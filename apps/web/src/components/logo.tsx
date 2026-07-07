import { SVGProps } from "react";

export function Logo(props: SVGProps<SVGSVGElement>) {
	return (
		<svg viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
			<rect width="256" height="256" rx="64" fill="#09090B"/>
			<rect x="2" y="2" width="252" height="252" rx="62" stroke="url(#paint0_linear)" strokeWidth="4"/>
			
			<path d="M72 104L104 136L72 168" stroke="#E4E4E7" strokeWidth="24" strokeLinecap="round" strokeLinejoin="round"/>
			<path d="M128 168H176" stroke="#E4E4E7" strokeWidth="24" strokeLinecap="round" strokeLinejoin="round"/>
			
			<path d="M172 72L182 92L202 102L182 112L172 132L162 112L142 102L162 92L172 72Z" fill="#3B82F6"/>
			<path d="M142 66L146 74L154 78L146 82L142 90L138 82L130 78L138 74L142 66Z" fill="#8B5CF6"/>
			
			<defs>
				<linearGradient id="paint0_linear" x1="0" y1="0" x2="256" y2="256" gradientUnits="userSpaceOnUse">
					<stop stopColor="#52525B" stopOpacity="0.8"/>
					<stop offset="1" stopColor="#18181B" stopOpacity="0.2"/>
				</linearGradient>
			</defs>
		</svg>
	);
}
