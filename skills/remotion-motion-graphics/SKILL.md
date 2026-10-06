---
name: remotion-motion-graphics
description: Create, edit, or improve videos and motion graphics in Remotion. Use when working on a Remotion composition, video render, animated title, social video, captions, or a visual polish pass. For simple cuts or transcodes outside Remotion, use the project's existing media tools.
---

# Remotion motion graphics

Make the video serve its message and audience. Use Remotion for frame-driven composition, then review the moving result and revise it. A technically valid render is not a finished video.

## Start with the brief and the project

- Inspect the existing project, package versions, assets, composition IDs, and user edits before changing code. Preserve its structure and design system unless the request calls for a change.
- Establish audience, platform, aspect ratio, length, message, call to action, brand rules, supplied footage/audio, and delivery format. Make a short beat plan or storyboard for a multi-scene video. Label unverified claims and placeholder assets.
- If a reference video is supplied, identify its pacing, hierarchy, camera language, typography, and sound. Use those observations as design criteria, not as a template to copy wholesale.
- Check the current [Remotion Agent Skills](https://github.com/remotion-dev/skills) and [Remotion docs](https://www.remotion.dev/docs/) for APIs affected by the task. Their `remotion-markup`, `remotion-render`, `remotion-captions`, and `remotion-multimedia` guidance covers implementation details that change over time. Do not install another skill or upgrade a project merely to read guidance.

## Resolve creative uncertainty cheaply

- Set a production time and cost budget using the user's constraints; if none are supplied, state a proportionate working limit. Identify the main uncertainty, such as the opening, pacing, or how to show a complex workflow.
- When that uncertainty could materially change the cut, compare two short treatments of the same segment with the same message and available approved assets. Use inexpensive previews and temporary narration; compare clarity, pacing, readability, and brand fit before developing the stronger direction. Skip variants for a settled direction or a small edit.
- Generate new music, voice, or imagery only when the selected direction needs it and the generation is within the authorized scope and budget. Review a rough cut before expensive asset generation or full-quality rendering. Do not deliver temporary narration or placeholder assets as approved material.

## Ground demos and updates in evidence

For product demos, terminal walkthroughs, and progress updates, read the demo and update criteria in [design-rules.md](references/design-rules.md). Build the story from verified behavior and existing project records; link each demonstrated claim to its source revision and capture. A narrated claim or reconstructed execution is not verification.

## Design and build

- Match motion to the tone: restrained movement, hard cuts, linear movement, still images, or silence can be deliberate. Avoid adding grain, glow, constant motion, transitions, or sound effects by default.
- Give each scene one clear visual priority. Vary shot scale and pacing; leave enough time to read text. Use meaningful transitions and animate only properties that help reveal information or direct attention.
- Use approved logos, colors, fonts, and footage as provided. Do not redraw or recolor protected brand assets. Verify licenses and provenance for new music, footage, fonts, and generated imagery before delivery.
- Drive animation from `useCurrentFrame()` and `useVideoConfig()` so preview and render agree. Avoid CSS animations and transitions for rendered motion. Clamp an interpolation where values must stop at a boundary; use easing or springs when they suit the movement.
- For new media code, check the current `@remotion/media` `Video` and `Audio` guidance. Use `OffthreadVideo` only when its documented behavior fits the project or an existing implementation requires it. Keep compatible Remotion packages on the same version; add packages with the project's package manager and Remotion's documented version guidance.
- Use `staticFile()` for local assets in `public/`. Load fonts deterministically. Inspect media metadata before setting trims, playback rate, or composition duration. Keep scene and audio timing in sync, including transition overlaps.
- For a new unbranded composition, [theme.ts](assets/theme.ts) is an optional token starter. Existing project tokens and approved brand rules take priority.
- Read [motion-patterns.md](references/motion-patterns.md) for optional creative patterns and implementation traps. Read [design-rules.md](references/design-rules.md) when planning a new video or assessing a polish pass. Copy a pattern only after adapting it to the project's Remotion version and the brief.

## Review loop

1. Preview the composition in Studio. Check the opening, each scene boundary, text holds, captions, final frame, and audio cues at normal speed. Use slow playback to inspect a specific timing problem.
2. Render representative stills early, then render the full video. Inspect stills for cropping, contrast, font loading, overlays, and safe areas. Watch the encoded video from start to finish with sound, including cuts and the ending.
3. Record the concrete issue and change one related decision at a time: timing, hierarchy, asset choice, motion, sound, or readability. Render again and inspect the affected moments plus the full cut. Continue until the brief and delivery checks pass or the working budget is reached; report unresolved issues rather than polishing indefinitely. Record which source revision, assets, and rendered output were reviewed. Relevant changes invalidate affected checks, including timing changes that affect captions and audio.

For a quick still check, use the installed Remotion CLI. Recent versions accept a comma-separated frame list:

```bash
npx remotion render <composition-id> out/review --frames=0,30,90 --image-format=png
```

Check the installed CLI's `render` and `still` help before relying on newer flags. Choose codec, quality, transparency, and dimensions for the actual destination; do not use one preset for every platform. If a render cannot run, say exactly what was verified and what still needs visual or audio review.

## Handoff

Provide the output path, composition ID, dimensions, fps, duration, codec, source and license notes for new assets, and any unresolved limitations. Keep the editable project and final render together when the user needs to revise the video later. When a direction is accepted, retain an approved example and its concrete corrections in project-local records for future reuse; do not copy private material into the shared skill or public repository.
