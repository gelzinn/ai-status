import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { CodeBlock } from "@/components/code-block";
import { HighlightedCodeBlock } from "@/components/code-highlight";
import { LIB_NAME } from "@/lib/env";
import { WAYBAR_CUSTOM_MODULE, WAYBAR_LOGO_MODULE, WAYBAR_LAYOUT } from "@/lib/waybar-config";

export function WaybarConfiguration() {
  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">
          Waybar Configuration
        </h2>
        <p className="max-w-xl text-muted-foreground">
          Add the module to your Waybar config to get started. The status
          bar shows the usage percentage of the active provider.
        </p>
      </div>

      <HighlightedCodeBlock
        code={WAYBAR_CUSTOM_MODULE}
        lang="json"
        label="~/.config/waybar/config.jsonc"
      />

      <p className="text-sm text-muted-foreground">
        To also show the active provider's logo — and get the same
        breakdown when you hover it — add the image module. The one-command
        install with{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          --icon-mode logo
        </code>{" "}
        sets this up for you.
      </p>

      <p className="text-sm text-muted-foreground">
        To do it by hand: the{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          exec
        </code>{" "}
        prints the logo path and its tooltip,{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          interval
        </code>{" "}
        keeps it refreshed, and you need an SVG rasterizer (imagemagick or
        librsvg). Then enable logo mode in the config TUI (right-click the
        module, set{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          Provider Icon
        </code>{" "}
        to{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          Provider Logo
        </code>
        ):
      </p>

      <HighlightedCodeBlock
        code={WAYBAR_LOGO_MODULE}
        lang="json"
        label="~/.config/waybar/config.jsonc"
      />

      <p className="text-sm text-muted-foreground">
        Then, include both{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          {`"image#${LIB_NAME}"`}
        </code>{" "}
        and{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          {`"custom/${LIB_NAME}"`}
        </code>{" "}
        in your preferred layout section (e.g.{" "}
        <code className="bg-secondary/50 px-1.5 py-0.5 rounded-md text-foreground font-mono">
          modules-right
        </code>
        ):
      </p>

      <CodeBlock
        code={WAYBAR_LAYOUT}
        label="~/.config/waybar/config.jsonc"
      >
        <pre>
          <code>
        <span className="text-muted-foreground/40">{"{\n"}</span>
        <span className="text-muted-foreground/30">{"    // ...\n"}</span>
        <span className="text-muted-foreground/40">
          {'    "modules-right": [\n'}
        </span>
        {"        "}
        <span className="text-[#ffcfa3]">{`"image#${LIB_NAME}"`}</span>
        <span className="text-muted-foreground/40">{",\n"}</span>
        {"        "}
        <span className="text-[#ffcfa3]">{`"custom/${LIB_NAME}"`}</span>
        <span className="text-muted-foreground/40">{",\n"}</span>
        <span className="text-muted-foreground/40">
          {'        "network",\n'}
        </span>
        <span className="text-muted-foreground/40">
          {'        "cpu",\n'}
        </span>
        <span className="text-muted-foreground/40">
          {'        "memory",\n'}
        </span>
        <span className="text-muted-foreground/40">
          {'        "clock",\n'}
        </span>
        <span className="text-muted-foreground/40">
          {'        "tray"\n'}
        </span>
        <span className="text-muted-foreground/40">{"    ],\n"}</span>
        <span className="text-muted-foreground/30">{"    // ...\n"}</span>
        <span className="text-muted-foreground/40">{"}"}</span>
          </code>
        </pre>
      </CodeBlock>

      <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm font-medium">
        <Link href="/linux" className="inline-flex items-center gap-1 transition-colors hover:text-muted-foreground">
          Linux installation and configuration <ArrowRight className="size-3.5" />
        </Link>
        <Link href="/linux/llms.txt" className="inline-flex items-center gap-1 transition-colors hover:text-muted-foreground">
          Copy-paste Linux guide for LLMs <ArrowRight className="size-3.5" />
        </Link>
      </div>
    </section>
  );
}
