"""Render macos/LearnHarness.icns: a dark tile with a small premise → conclusion hypergraph (two premises joined
by an ∧ hub, rising to a conclusion) in the app's emerald / indigo / amber palette. Uses AppKit via PyObjC."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from AppKit import (NSBezierPath, NSBitmapImageRep, NSColor, NSCompositingOperationSourceOver, NSGradient,
                    NSGraphicsContext, NSPNGFileType)
from Foundation import NSMakeRect, NSPoint

OUT = Path(__file__).resolve().parent / "LearnHarness.icns"


def rgb(h: str, a: float = 1.0) -> NSColor:
    h = h.lstrip("#")
    return NSColor.colorWithSRGBRed_green_blue_alpha_(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def render(size: int, path: Path) -> None:
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, "NSDeviceRGBColorSpace", 0, 0)
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    ctx.setCompositingOperation_(NSCompositingOperationSourceOver)
    s = size / 1024.0

    def P(x: float, y: float) -> NSPoint:
        return NSPoint(x * s, y * s)

    tile = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(NSMakeRect(100 * s, 100 * s, 824 * s, 824 * s), 185 * s, 185 * s)
    NSGradient.alloc().initWithStartingColor_endingColor_(rgb("#131c33"), rgb("#070a12")).drawInBezierPath_angle_(tile, -90)
    rgb("#1e293b").setStroke()
    tile.setLineWidth_(6 * s)
    tile.stroke()

    a, b, hub, c = P(300, 300), P(724, 300), P(512, 520), P(512, 735)
    for p, col in ((a, "#6366f1"), (b, "#06b6d4")):
        line = NSBezierPath.bezierPath()
        line.moveToPoint_(p)
        line.lineToPoint_(hub)
        line.setLineWidth_(26 * s)
        line.setLineCapStyle_(1)
        rgb(col, 0.95).setStroke()
        line.stroke()
    up = NSBezierPath.bezierPath()
    up.moveToPoint_(hub)
    up.lineToPoint_(P(512, 660))
    up.setLineWidth_(30 * s)
    rgb("#10b981").setStroke()
    up.stroke()
    head = NSBezierPath.bezierPath()
    head.moveToPoint_(P(512, 690))
    head.lineToPoint_(P(462, 625))
    head.lineToPoint_(P(562, 625))
    head.closePath()
    rgb("#10b981").setFill()
    head.fill()
    d = NSBezierPath.bezierPath()
    for x, y in ((512, 575), (557, 520), (512, 465), (467, 520)):
        (d.moveToPoint_ if d.isEmpty() else d.lineToPoint_)(P(x, y))
    d.closePath()
    rgb("#0b1222").setFill()
    d.fill()
    rgb("#f8fafc").setStroke()
    d.setLineWidth_(10 * s)
    d.stroke()

    def node(p: NSPoint, r: float, fill: str, ring: str) -> None:
        o = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(p.x - r * s, p.y - r * s, 2 * r * s, 2 * r * s))
        rgb(fill).setFill()
        o.fill()
        rgb(ring).setStroke()
        o.setLineWidth_(14 * s)
        o.stroke()

    node(a, 70, "#4f46e5", "#a5b4fc")
    node(b, 70, "#0891b2", "#67e8f9")
    node(c, 92, "#059669", "#6ee7b7")
    ring = NSBezierPath.bezierPath()
    ring.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(c, 128 * s, 90, -150, True)
    ring.setLineWidth_(16 * s)
    ring.setLineCapStyle_(1)
    rgb("#f59e0b").setStroke()
    ring.stroke()

    NSGraphicsContext.restoreGraphicsState()
    rep.representationUsingType_properties_(NSPNGFileType, {}).writeToFile_atomically_(str(path), True)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "LearnHarness.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            render(base, iconset / f"icon_{base}x{base}.png")
            render(base * 2, iconset / f"icon_{base}x{base}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUT)], check=True)
        if "--png" in sys.argv:
            render(1024, OUT.with_suffix(".png"))
    print(OUT)


if __name__ == "__main__":
    main()
