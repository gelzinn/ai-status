import os
import base64

SPARK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "assets", "spark")
NUM_FRAMES = 8
ANIM_DURATION = 0.889

def generate_css():
    frames = []
    for i in range(NUM_FRAMES):
        path = os.path.join(SPARK_DIR, f"spark-{i}.png")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            frames.append(b64)

    pct_step = 100 // NUM_FRAMES

    lines = ["@keyframes claude-spark {"]
    for i, b64 in enumerate(frames):
        pct = i * pct_step
        lines.append(f"  {pct}% {{ background-image: url(\"data:image/png;base64,{b64}\"); }}")
    lines.append("}")

    lines.append("")
    lines.append("#custom-ai-status.claude-spark {")
    lines.append("  animation: claude-spark %.3fs infinite;" % ANIM_DURATION)
    lines.append("  background-size: 20px;")
    lines.append("  background-repeat: no-repeat;")
    lines.append("  background-position: left center;")
    lines.append("  padding-left: 24px;")
    lines.append("  min-width: 20px;")
    lines.append("}")

    return "\n".join(lines) + "\n"

def main():
    css = generate_css()
    config_dir = os.path.expanduser("~/.config/waybar")
    os.makedirs(config_dir, exist_ok=True)
    path = os.path.join(config_dir, "spark.css")
    with open(path, "w") as f:
        f.write(css)
    print("Generated", path)

if __name__ == "__main__":
    main()
