---
name: claude-speed-reader
description: "Enables rapid serial visual presentation (RSVP) speed reading of Claude responses at 600+ WPM with Spritz-style optimal recognition point (ORP) highlighting. Configurable WPM speed, font sizes, and pausing at punctuation. Use when speed reading Claude's responses, reading long outputs faster, enabling RSVP mode for verbose answers, configuring fast reading with WPM control, processing lengthy responses quickly, or skimming while retaining comprehension."
type: feature
source: "https://github.com/SeanZoR/claude-speed-reader"
risk: safe
user-invocable: true
---

# Claude Speed Reader

Transform reading speed from 200 WPM (normal) to 600+ WPM using RSVP (Rapid Serial Visual Presentation) with Spritz-style ORP (Optimal Recognition Point) highlighting.

## How RSVP Speed Reading Works

Traditional reading: Eyes scan across a line (200-300 WPM typical)
RSVP approach: One word at a time, centered with ORP highlighted (600+ WPM possible)

The ORP is the character your eye naturally focuses on—typically 30-40% into longer words. Highlighting this point dramatically reduces eye movement and improves comprehension at higher speeds.

## Configuration Options

### Speed (WPM)
- **300 WPM**: Brisk but conversational (training speed)
- **400 WPM**: Fast reading, good comprehension retention
- **600 WPM**: Speed reader's sweet spot (requires practice)
- **800+ WPM**: Expert only (high comprehension loss risk)

Start at 300 WPM, increase in 100 WPM increments as comfort increases.

### Punctuation Pausing
- **None**: Continuous flow (for fiction, narratives)
- **Short pause** (200ms): At commas and semicolons
- **Medium pause** (400ms): At periods and colons
- **Long pause** (800ms): At major breaks (full stop needed)

Pausing helps comprehension dramatically at 600+ WPM.

### Font Configuration
- **Font size**: 24-32pt recommended (larger = easier ORP tracking)
- **Font family**: Monospace or sans-serif with clear character definition
- **ORP color**: High contrast (e.g., red/yellow on white, white on dark)
- **Word width**: Limit display width to 1-3 words for fast reading

### Display Options
- **Centered display**: Word centered on screen (standard RSVP)
- **Guided view**: Shows context (previous + current + next word)
- **Background dimming**: Highlight word, dim context
- **Scrolling**: Auto-advance through long text or user-paced

## Reading Session Checklist

- [ ] Set initial WPM (start at 300)
- [ ] Enable punctuation pausing (medium if unsure)
- [ ] Configure font size (comfortable without straining)
- [ ] Choose display mode (centered for speed, guided for comprehension)
- [ ] Take baseline comprehension test at starting speed
- [ ] Increase WPM after successful session
- [ ] Track comprehension score vs. WPM (identify your optimal speed)

## Comprehension Tips

1. **Subvocalization**: Don't "say" words in your head—let eyes/brain process directly
2. **Fixation**: Keep eyes on ORP, don't follow word movement
3. **Practice**: Spend 5-10 min daily for 1-2 weeks before major speed jumps
4. **Content choice**: Start with expository writing (blogs, documentation), avoid dense philosophy/code
5. **Breaks**: Every 15-20 minutes at 600+ WPM (cognitive load is high)

## When to Use Speed Reading

✓ Long Claude responses that contain key info but are verbose
✓ Documentation or reference material you need quick insights from
✓ Blog posts or articles you're sampling for relevance
✓ Meeting notes or transcripts you need to review quickly

✗ Dense code or mathematical proofs (requires slower reading)
✗ Literary fiction where rhythm matters
✗ Anything requiring detailed analysis or annotation

See [source repository](https://github.com/SeanZoR/claude-speed-reader) for browser extensions and speed reading science research.
