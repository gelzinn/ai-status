#!/usr/bin/env python3
import pty
import os
import sys
import time
import select
import re
import fcntl
import termios
import struct

ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text):
    return ANSI_ESCAPE.sub('', text)

def set_size(fd, rows, cols):
    try:
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except:
        pass

def get_agy_usage():
    pid, fd = pty.fork()
    if pid == 0:
        try:
            os.execvp("agy", ["agy"])
        except:
            sys.exit(1)
    else:
        set_size(fd, 80, 120)

        output = b""
        start_time = time.time()
        prompt_sent = False
        prompt_sent_time = 0
        enter_sent = False
        exit_sent = False

        while True:
            elapsed = time.time() - start_time
            if elapsed > 15:
                break

            if prompt_sent and not enter_sent and (time.time() - prompt_sent_time > 1.5):
                try:
                    os.write(fd, b"\r")
                except:
                    pass
                enter_sent = True

            r, w, x = select.select([fd], [], [], 0.1)
            if fd in r:
                try:
                    data = os.read(fd, 4096)
                    if not data:
                        break
                    output += data
                    clean = strip_ansi(output.decode('utf-8', errors='replace'))

                    if "Welcome to the Antigravity CLI" in clean and not prompt_sent:
                        idx = clean.find("Welcome to the Antigravity CLI")
                        if ">" in clean[idx:]:
                            time.sleep(2.0)
                            try:
                                os.write(fd, b"/usage")
                            except:
                                pass
                            prompt_sent = True
                            prompt_sent_time = time.time()
                            start_time = time.time()

                    if enter_sent and "Weekly Limit" in clean and not exit_sent:
                        time.sleep(0.5)
                        try:
                            os.write(fd, b"/exit\r")
                        except:
                            pass
                        exit_sent = True
                except OSError:
                    break
            else:
                if exit_sent:
                    break

        try:
            os.close(fd)
        except:
            pass
        try:
            os.kill(pid, 9)
        except:
            pass

        return strip_ansi(output.decode('utf-8', errors='replace'))

def main():
    try:
        raw_out = get_agy_usage()
        print(raw_out)
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    main()
