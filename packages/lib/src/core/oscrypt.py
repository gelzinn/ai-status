"""Read Chromium OSCrypt tokens without shelling out with secret arguments.

AES is used only to read an existing application's tokens. All operations are
in memory; this module never writes an application credential or encryption key.
"""
import base64
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys


def _mul(a, b):
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        a = ((a << 1) ^ (0x11b if a & 128 else 0)) & 255
        b >>= 1
    return result


def _sbox():
    result = []
    for value in range(256):
        inverse, power, exponent = 1, value, 254
        while exponent:
            if exponent & 1:
                inverse = _mul(inverse, power)
            power = _mul(power, power)
            exponent >>= 1
        inverse = inverse if value else 0
        out = inverse
        for shift in range(1, 5):
            out ^= ((inverse << shift) | (inverse >> (8 - shift))) & 255
        result.append(out ^ 0x63)
    return result


_S = _sbox()
_I = [_S.index(value) for value in range(256)]


def _keys(key):
    words = [list(key[i:i+4]) for i in range(0, len(key), 4)]
    nk = len(words)
    if nk not in (4, 8):
        raise ValueError("Unsupported encryption key")
    rounds = nk + 6
    rcon = 1
    for i in range(nk, 4 * (rounds + 1)):
        word = words[-1][:]
        if i % nk == 0:
            word = [_S[value] for value in word[1:] + word[:1]]
            word[0] ^= rcon
            rcon = _mul(rcon, 2)
        elif nk == 8 and i % nk == 4:
            word = [_S[value] for value in word]
        words.append([a ^ b for a, b in zip(words[i-nk], word)])
    return [sum(words[i:i+4], []) for i in range(0, len(words), 4)]


def _block(block, keys, decrypt=False):
    state = list(block)
    key_order = list(reversed(keys)) if decrypt else keys
    state = [a ^ b for a, b in zip(state, key_order[0])]
    for round_index, key in enumerate(key_order[1:], 1):
        if decrypt:
            state = [state[4*((column-row)%4)+row] for column in range(4) for row in range(4)]
            state = [_I[value] for value in state]
            state = [a ^ b for a, b in zip(state, key)]
        else:
            state = [_S[value] for value in state]
            state = [state[4*((column+row)%4)+row] for column in range(4) for row in range(4)]
        if round_index < len(keys)-1:
            coefficients = (14, 11, 13, 9) if decrypt else (2, 3, 1, 1)
            state = [_mul(state[4*column], coefficients[(-row)%4]) ^
                     _mul(state[4*column+1], coefficients[(1-row)%4]) ^
                     _mul(state[4*column+2], coefficients[(2-row)%4]) ^
                     _mul(state[4*column+3], coefficients[(3-row)%4])
                     for column in range(4) for row in range(4)]
        if not decrypt:
            state = [a ^ b for a, b in zip(state, key)]
    return bytes(state)


def decrypt_cbc(blob, key):
    if not blob or len(blob) % 16:
        raise ValueError("Invalid encrypted token")
    keys, previous, result = _keys(key), b' ' * 16, bytearray()
    for offset in range(0, len(blob), 16):
        current = blob[offset:offset+16]
        result.extend(a ^ b for a, b in zip(_block(current, keys, True), previous))
        previous = current
    padding = result[-1]
    if not 1 <= padding <= 16 or result[-padding:] != bytes([padding])*padding:
        raise ValueError("Invalid encrypted token")
    return bytes(result[:-padding])


def _galois(a, b):
    result = 0
    for index in range(128):
        if a & (1 << (127-index)):
            result ^= b
        b = (b >> 1) ^ (0xe1000000000000000000000000000000 if b & 1 else 0)
    return result


def decrypt_gcm(blob, key):
    nonce, encrypted, tag = blob[:12], blob[12:-16], blob[-16:]
    if len(blob) < 28:
        raise ValueError("Invalid encrypted token")
    keys = _keys(key)
    hash_key = int.from_bytes(_block(bytes(16), keys), 'big')
    auth = 0
    for offset in range(0, len(encrypted), 16):
        auth = _galois(auth ^ int.from_bytes(encrypted[offset:offset+16].ljust(16, b'\0'), 'big'), hash_key)
    auth = _galois(auth ^ (len(encrypted)*8), hash_key)
    initial = nonce + b'\0\0\0\1'
    expected = bytes(a ^ b for a, b in zip(auth.to_bytes(16, 'big'), _block(initial, keys)))
    if not hmac.compare_digest(tag, expected):
        raise ValueError("Invalid encrypted token")
    result = bytearray()
    for offset in range(0, len(encrypted), 16):
        stream = _block(nonce + (offset//16+2).to_bytes(4, 'big'), keys)
        result.extend(a ^ b for a, b in zip(encrypted[offset:offset+16], stream))
    return bytes(result)


def _secret(args):
    try:
        result = subprocess.run(args, capture_output=True, timeout=4, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _windows_key(path):
    master = base64.b64decode(json.loads((path.parent / 'Local State').read_text(encoding='utf-8'))['os_crypt']['encrypted_key'])
    if not master.startswith(b'DPAPI'):
        raise ValueError("Invalid encryption key")
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint32), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    source = (ctypes.c_ubyte * (len(master)-5)).from_buffer_copy(master[5:])
    incoming, outgoing = Blob(len(source), source), Blob()
    unprotect = ctypes.windll.crypt32.CryptUnprotectData
    unprotect.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(Blob)]
    unprotect.restype = ctypes.c_int
    free = ctypes.windll.kernel32.LocalFree
    free.argtypes, free.restype = [ctypes.c_void_p], ctypes.c_void_p
    if not unprotect(ctypes.byref(incoming), None, None, None, None, 0, ctypes.byref(outgoing)):
        raise ValueError("Unable to read encryption key")
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        free(outgoing.data)


def grok_bot_tokens(path):
    root = json.loads(Path(path).read_text(encoding='utf-8'))['cursor-accounts']
    if isinstance(root, str):
        root = json.loads(root)
    entry = root['accounts'][root['active']]
    blobs = [base64.b64decode(entry[name], validate=True) for name in ('cursor-access-token', 'cursor-refresh-token')]
    if any(blob[:3] not in (b'v10', b'v11') for blob in blobs):
        raise ValueError("Invalid encrypted token")
    if os.name == 'nt':
        key = _windows_key(Path(path))
        return tuple(decrypt_gcm(blob[3:], key).decode('utf-8') for blob in blobs)
    if sys.platform == 'darwin':
        secret = _secret(['/usr/bin/security', 'find-generic-password', '-s', 'Grok Bot Safe Storage', '-a', 'Grok Bot Key', '-w'])
        secrets, iterations = [secret] if secret else [], 1003
    else:
        secret = _secret(['secret-tool', 'lookup', 'application', 'Grok Bot'])
        secrets, iterations = ([secret] if secret else []) + [b'peanuts'], 1
    for secret in secrets:
        try:
            key = hashlib.pbkdf2_hmac('sha1', secret, b'saltysalt', iterations, 16)
            return tuple(decrypt_cbc(blob[3:], key).decode('utf-8') for blob in blobs)
        except (ValueError, UnicodeError):
            continue
    raise ValueError("Unable to read encrypted session")
