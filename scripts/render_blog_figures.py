#!/usr/bin/env python3
"""Render blog figure JSON specs into HTML and PNG.

Usage:
  python3 scripts/render_blog_figures.py \
    images/posts/mempalace_research/specs/*.json \
    --out-dir images/posts/mempalace_research
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path


FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", '
    '"Hiragino Sans GB", "Microsoft YaHei", sans-serif'
)


def h(text: str) -> str:
    return html.escape(text, quote=True)


def lines_block(tag: str, class_name: str, lines: list[str]) -> str:
    inner = "".join(f"<div>{h(line)}</div>" for line in lines)
    return f'<{tag} class="{class_name}">{inner}</{tag}>'


def render_contrast_panels(spec: dict) -> str:
    left_boxes = []
    for idx, box in enumerate(spec["left"]["boxes"]):
        bg = spec["left"]["box_backgrounds"][idx]
        left_boxes.append(
            f"""
            <div class="box" style="background:{bg}; border-color:{spec['left']['stroke']};">
              <div class="box-title">{h(box['title'])}</div>
              {lines_block("div", "box-body", box["body_lines"])}
            </div>
            """
        )
        if idx < len(spec["left"]["boxes"]) - 1:
            left_boxes.append('<div class="arrow left"></div>')

    right_split_boxes = []
    for box in spec["right"]["split_boxes"]:
        right_split_boxes.append(
            f"""
            <div class="box split-card" style="background:{box['background']}; border-color:{spec['right']['stroke']};">
              <div class="box-title">{h(box['title'])}</div>
              {lines_block("div", "box-body", box["body_lines"])}
            </div>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(spec['meta']['title'])}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: {FONT_STACK};
      background: {spec['theme']['background']};
      color: {spec['theme']['text']};
    }}
    .canvas {{
      width: {spec['meta']['width']}px;
      height: {spec['meta']['height']}px;
      margin: 0 auto;
      padding: 44px 56px 32px;
      position: relative;
      overflow: hidden;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.18;
      font-weight: 700;
      letter-spacing: -.02em;
      max-width: 1040px;
    }}
    .subtitle {{
      margin-top: 12px;
      font-size: 18px;
      line-height: 1.45;
      color: {spec['theme']['muted']};
      max-width: 980px;
    }}
    .subtitle div {{ margin: 0; }}
    .columns {{
      margin-top: 30px;
      display: grid;
      grid-template-columns: 500px 536px;
      gap: 48px;
      align-items: start;
    }}
    .panel {{
      border-radius: 24px;
      padding: 28px;
      border: 3px solid;
      min-height: 540px;
      position: relative;
    }}
    .panel.left {{
      background: {spec['left']['background']};
      border-color: {spec['left']['stroke']};
    }}
    .panel.right {{
      background: {spec['right']['background']};
      border-color: {spec['right']['stroke']};
    }}
    .panel-title {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      font-weight: 700;
    }}
    .panel-subtitle {{
      margin-top: 10px;
      font-size: 16px;
      line-height: 1.45;
      color: {spec['theme']['muted']};
    }}
    .stack {{
      margin-top: 26px;
      display: grid;
      gap: 18px;
    }}
    .box {{
      border-radius: 18px;
      border: 2.5px solid;
      padding: 18px 20px;
      min-height: 92px;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}
    .box-title {{
      font-size: 18px;
      line-height: 1.35;
      font-weight: 600;
      color: {spec['theme']['box_text']};
    }}
    .box-body {{
      margin-top: 8px;
      font-size: 16px;
      line-height: 1.4;
      color: {spec['theme']['muted']};
    }}
    .box-body div + div {{ margin-top: 4px; }}
    .arrow {{
      width: 4px;
      height: 28px;
      border-radius: 999px;
      margin: 0 auto;
      position: relative;
    }}
    .arrow::after {{
      content: "";
      position: absolute;
      left: 50%;
      bottom: -6px;
      transform: translateX(-50%);
      border-left: 7px solid transparent;
      border-right: 7px solid transparent;
      border-top: 10px solid currentColor;
    }}
    .arrow.left {{ background: {spec['left']['arrow']}; color: {spec['left']['arrow']}; }}
    .arrow.right {{ background: {spec['right']['arrow']}; color: {spec['right']['arrow']}; }}
    .split {{
      margin-top: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    .split-card {{
      min-height: 112px;
    }}
    .note {{
      position: absolute;
      left: 56px;
      right: 56px;
      bottom: 26px;
      font-size: 18px;
      line-height: 1.45;
      font-weight: 600;
      color: {spec['theme']['text']};
    }}
    .callout {{
      position: absolute;
      left: 562px;
      top: 394px;
      width: 90px;
      text-align: center;
      font-size: 16px;
      line-height: 1.45;
      color: {spec['theme']['muted']};
    }}
    .callout div + div {{ margin-top: 6px; }}
  </style>
</head>
<body>
  <div class="canvas">
    {lines_block("h1", "", spec["meta"]["title_lines"])}
    {lines_block("div", "subtitle", spec["meta"]["subtitle_lines"])}

    <div class="columns">
      <section class="panel left">
        <div class="panel-title">{h(spec['left']['title'])}</div>
        <div class="panel-subtitle">{h(spec['left']['subtitle'])}</div>
        <div class="stack">
          {''.join(left_boxes)}
        </div>
      </section>

      <section class="panel right">
        <div class="panel-title">{h(spec['right']['title'])}</div>
        <div class="panel-subtitle">{h(spec['right']['subtitle'])}</div>
        <div class="stack">
          <div class="box" style="background:{spec['right']['top_box']['background']}; border-color:{spec['right']['stroke']};">
            <div class="box-title">{h(spec['right']['top_box']['title'])}</div>
            {lines_block("div", "box-body", spec["right"]["top_box"]["body_lines"])}
          </div>
          <div class="arrow right"></div>
          <div class="split">
            {''.join(right_split_boxes)}
          </div>
          <div class="arrow right"></div>
          <div class="box" style="background:{spec['right']['bottom_box']['background']}; border-color:{spec['right']['bottom_box']['stroke']}; min-height:94px;">
            <div class="box-title">{h(spec['right']['bottom_box']['title'])}</div>
            {lines_block("div", "box-body", spec["right"]["bottom_box"]["body_lines"])}
          </div>
        </div>
      </section>
    </div>

    {lines_block("div", "callout", spec["middle_note_lines"])}
    {lines_block("div", "note", spec["footer_lines"])}
  </div>
</body>
</html>
"""


def render_memory_stack(spec: dict) -> str:
    left_cards = []
    for card in spec["left_cards"]:
        left_cards.append(
            f"""
            <div class="card" style="background:{card['background']}; border-color:{card['stroke']};">
              <div class="card-title">{h(card['title'])}</div>
              {lines_block("div", "card-body", card["body_lines"])}
            </div>
            """
        )

    steps = []
    for idx, step in enumerate(spec["steps"]):
        steps.append(
            f"""
            <div class="card" style="background:{step['background']}; border-color:{step['stroke']};">
              <div class="step-title">{h(step['title'])}</div>
              {lines_block("div", "card-body", step["body_lines"])}
            </div>
            """
        )
        if idx < len(spec["steps"]) - 1:
            steps.append('<div class="arrow"></div>')

    final_cards = []
    for card in spec["final_cards"]:
        final_cards.append(
            f"""
            <div class="card final-card" style="background:{card['background']}; border-color:{card['stroke']};">
              <div class="step-title">{h(card['title'])}</div>
              {lines_block("div", "card-body", card["body_lines"])}
            </div>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(spec['meta']['title'])}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: {FONT_STACK};
      background: {spec['theme']['background']};
      color: {spec['theme']['text']};
    }}
    .canvas {{
      width: {spec['meta']['width']}px;
      height: {spec['meta']['height']}px;
      margin: 0 auto;
      padding: 44px 56px 36px;
      overflow: hidden;
      position: relative;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.18;
      font-weight: 700;
      max-width: 1040px;
      letter-spacing: -.02em;
    }}
    .subtitle {{
      margin-top: 12px;
      font-size: 18px;
      line-height: 1.45;
      color: {spec['theme']['muted']};
      max-width: 1040px;
    }}
    .subtitle div {{ margin: 0; }}
    .columns {{
      margin-top: 30px;
      display: grid;
      grid-template-columns: 520px 492px;
      gap: 52px;
      align-items: start;
    }}
    .panel {{
      background: {spec['theme']['panel']};
      border: 3px solid {spec['theme']['stroke']};
      border-radius: 24px;
      padding: 28px;
      min-height: 560px;
    }}
    .panel-title {{
      margin: 0 0 24px;
      font-size: 24px;
      line-height: 1.2;
      font-weight: 700;
    }}
    .stack, .steps {{
      display: grid;
      gap: 20px;
    }}
    .card {{
      border-radius: 18px;
      padding: 18px 20px;
      border: 2.5px solid;
    }}
    .card-title {{
      font-size: 20px;
      line-height: 1.3;
      font-weight: 700;
      color: {spec['theme']['text']};
    }}
    .step-title {{
      font-size: 18px;
      line-height: 1.35;
      font-weight: 600;
      color: {spec['theme']['text']};
    }}
    .card-body {{
      margin-top: 8px;
      font-size: 16px;
      line-height: 1.45;
      color: {spec['theme']['muted2']};
    }}
    .card-body div + div {{ margin-top: 4px; }}
    .arrow {{
      width: 4px;
      height: 26px;
      border-radius: 999px;
      background: {spec['theme']['arrow']};
      margin: 0 auto;
      position: relative;
    }}
    .arrow::after {{
      content: "";
      position: absolute;
      left: 50%;
      bottom: -6px;
      transform: translateX(-50%);
      border-left: 7px solid transparent;
      border-right: 7px solid transparent;
      border-top: 10px solid {spec['theme']['arrow']};
    }}
    .small-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }}
    .note {{
      position: absolute;
      left: 56px;
      right: 56px;
      bottom: 24px;
      font-size: 18px;
      line-height: 1.45;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="canvas">
    {lines_block("h1", "", spec["meta"]["title_lines"])}
    {lines_block("div", "subtitle", spec["meta"]["subtitle_lines"])}

    <div class="columns">
      <section class="panel">
        <div class="panel-title">{h(spec['left_title'])}</div>
        <div class="stack">
          {''.join(left_cards)}
        </div>
      </section>

      <section class="panel">
        <div class="panel-title">{h(spec['right_title'])}</div>
        <div class="steps">
          {''.join(steps)}
          <div class="small-grid">
            {''.join(final_cards)}
          </div>
        </div>
      </section>
    </div>

    {lines_block("div", "note", spec["footer_lines"])}
  </div>
</body>
</html>
"""


def render_timeline_lanes(spec: dict) -> str:
    lane_html = []
    for lane in spec["lanes"]:
        events = []
        for event in lane["events"]:
            events.append(
                f"""
                <div class="event" style="width:{event['width']}px;">
                  <div class="date">{h(event['date'])}</div>
                  <div class="dot" style="background:{lane['color']};"></div>
                  <div class="card" style="background:{lane['background']}; border-color:{lane['color']};">
                    <div class="card-title">{h(event['title'])}</div>
                    {lines_block("div", "card-body", event["body_lines"])}
                  </div>
                </div>
                """
            )
        lane_html.append(
            f"""
            <section class="lane">
              <div class="lane-name">{h(lane['name'])}</div>
              <div class="track">
                <div class="events">
                  {''.join(events)}
                </div>
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(spec['meta']['title'])}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: {FONT_STACK};
      background: {spec['theme']['background']};
      color: {spec['theme']['text']};
    }}
    .canvas {{
      width: {spec['meta']['width']}px;
      height: {spec['meta']['height']}px;
      margin: 0 auto;
      padding: 44px 56px 32px;
      position: relative;
      overflow: hidden;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.18;
      font-weight: 700;
      max-width: 1040px;
      letter-spacing: -.02em;
    }}
    .subtitle {{
      margin-top: 12px;
      font-size: 18px;
      line-height: 1.45;
      color: {spec['theme']['muted']};
      max-width: 1040px;
    }}
    .subtitle div {{ margin: 0; }}
    .lanes {{
      margin-top: 34px;
      display: grid;
      gap: 48px;
    }}
    .lane {{
      display: grid;
      grid-template-columns: 104px 1fr;
      gap: 20px;
      align-items: start;
    }}
    .lane-name {{
      font-size: 22px;
      line-height: 1.2;
      font-weight: 700;
      padding-top: 38px;
    }}
    .track {{
      position: relative;
      min-height: 132px;
      padding-top: 10px;
    }}
    .track::before {{
      content: "";
      position: absolute;
      left: 0;
      right: 0;
      top: 52px;
      height: 4px;
      background: {spec['theme']['line']};
      border-radius: 999px;
    }}
    .events {{
      position: relative;
      display: flex;
      gap: 22px;
      align-items: flex-start;
    }}
    .event {{
      position: relative;
      min-width: 0;
    }}
    .date {{
      margin: 0 0 10px 8px;
      font-size: 15px;
      line-height: 1.3;
      color: {spec['theme']['muted']};
    }}
    .dot {{
      width: 30px;
      height: 30px;
      border-radius: 50%;
      position: absolute;
      left: 0;
      top: 38px;
      z-index: 2;
    }}
    .card {{
      margin-left: 22px;
      border-radius: 18px;
      padding: 16px 18px;
      border: 2.5px solid;
      min-height: 82px;
    }}
    .card-title {{
      font-size: 18px;
      line-height: 1.35;
      font-weight: 600;
    }}
    .card-body {{
      margin-top: 8px;
      font-size: 15px;
      line-height: 1.45;
      color: {spec['theme']['muted']};
    }}
    .card-body div + div {{ margin-top: 4px; }}
    .note {{
      position: absolute;
      left: 56px;
      right: 56px;
      bottom: 20px;
      font-size: 18px;
      line-height: 1.45;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="canvas">
    {lines_block("h1", "", spec["meta"]["title_lines"])}
    {lines_block("div", "subtitle", spec["meta"]["subtitle_lines"])}
    <div class="lanes">
      {''.join(lane_html)}
    </div>
    {lines_block("div", "note", spec["footer_lines"])}
  </div>
</body>
</html>
"""


def render_spec(spec: dict) -> str:
    kind = spec["kind"]
    if kind == "contrast_panels":
        return render_contrast_panels(spec)
    if kind == "memory_stack":
        return render_memory_stack(spec)
    if kind == "timeline_lanes":
        return render_timeline_lanes(spec)
    raise ValueError(f"Unsupported figure kind: {kind}")


def screenshot_html(html_path: Path, png_path: Path, width: int, height: int, browser: str) -> None:
    uri = html_path.resolve().as_uri()
    subprocess.run(
        [
            "playwright",
            "screenshot",
            "-b",
            browser,
            "--viewport-size",
            f"{width},{height}",
            "--wait-for-timeout",
            "400",
            uri,
            str(png_path),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render blog figure JSON specs to HTML and PNG.")
    parser.add_argument("specs", nargs="+", help="JSON spec files")
    parser.add_argument("--out-dir", required=True, help="Output directory for html/png")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "webkit", "firefox"])
    parser.add_argument("--html-only", action="store_true", help="Only generate HTML")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for spec_name in args.specs:
        spec_path = Path(spec_name)
        with spec_path.open("r", encoding="utf-8") as f:
            spec = json.load(f)

        stem = spec_path.stem
        html_path = out_dir / f"{stem}.html"
        png_path = out_dir / f"{stem}.png"

        html_doc = render_spec(spec)
        html_path.write_text(html_doc, encoding="utf-8")

        if not args.html_only:
            screenshot_html(html_path, png_path, spec["meta"]["width"], spec["meta"]["height"], args.browser)
            print(f"Rendered {png_path}")
        else:
            print(f"Wrote {html_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
