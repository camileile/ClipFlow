import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const iconDefaults = {
  fill: "none",
  viewBox: "0 0 24 24",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function ArrowRightIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export function ClipFlowIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M12 6v9m0 0 3-3m-3 3-3-3M7 18h10" />
    </svg>
  );
}
export function CheckIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <path d="m5 12 4 4L19 6" />
    </svg>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 20h14" />
    </svg>
  );
}

export function LinkIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1" />
      <path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1" />
    </svg>
  );
}

export function MoonIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <path d="M20.5 14.4A8 8 0 0 1 9.6 3.5 8.5 8.5 0 1 0 20.5 14.4Z" />
    </svg>
  );
}

export function PlayIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <path d="m9 7 8 5-8 5V7Z" />
    </svg>
  );
}

export function SparkleIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <path d="M12 3c.7 4.3 2.7 6.3 7 7-4.3.7-6.3 2.7-7 7-.7-4.3-2.7-6.3-7-7 4.3-.7 6.3-2.7 7-7Z" />
      <path d="M19 17c.2 1.2.8 1.8 2 2-1.2.2-1.8.8-2 2-.2-1.2-.8-1.8-2-2 1.2-.2 1.8-.8 2-2Z" />
    </svg>
  );
}

export function SunIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

export function VideoIcon(props: IconProps) {
  return (
    <svg {...iconDefaults} {...props}>
      <rect x="3" y="5" width="14" height="14" rx="3" />
      <path d="m17 10 4-2v8l-4-2" />
    </svg>
  );
}
