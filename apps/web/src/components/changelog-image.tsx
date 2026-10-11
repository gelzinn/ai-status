"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

export function ChangelogImage({ src, alt, zoomable = true }: { src: string; alt: string; zoomable?: boolean }) {
	const dialog = useRef<HTMLDialogElement>(null);
	const [open, setOpen] = useState(false);
	useEffect(() => {
		if (open) dialog.current?.showModal();
	}, [open]);
	if (!zoomable) return <img src={src} alt={alt} loading="lazy" />;
	return <>
		<button type="button" className="changelog-image" aria-label={`Enlarge ${alt || "release image"}`} onClick={() => setOpen(true)}>
			<img src={src} alt={alt} loading="lazy" />
		</button>
		{open && createPortal(<dialog ref={dialog} className="changelog-image-dialog" aria-label={alt || "Release image"} onClose={() => setOpen(false)} onClick={(event) => {
			if (event.target === event.currentTarget) dialog.current?.close();
		}}>
			<button type="button" aria-label="Close image" onClick={() => dialog.current?.close()}><X size={24} /></button>
			<img src={src} alt={alt} loading="lazy" />
		</dialog>, document.body)}
	</>;
}
