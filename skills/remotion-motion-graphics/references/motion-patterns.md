# Motion patterns and implementation traps

These are choices, not required layers or effects. Confirm API details in the [current Remotion docs](https://www.remotion.dev/docs/) and the project's installed version before copying code.

## Frame-driven timing

Use `useCurrentFrame()` and `useVideoConfig()` for rendered animation. Express a duration in seconds as `seconds * fps` when it should scale with frame rate. A few frames of staggering can clarify an ordered list; simultaneous motion can signal a single group. Clamp `interpolate()` at boundaries where overshoot would be incorrect, especially numbers, opacity, and scene exits. An unclamped counter can show a false value after its intended endpoint.

Avoid hooks inside `.map()` or conditionals. Put animated list items in child components. Keep animation state deterministic from frame, props, and assets so random render order does not change the result.

## Scene timing

Build a timeline that accounts for scene duration, transition overlap, captions, and sound. `TransitionSeries` shortens total duration by the overlapping transition duration; inspect its current rules before setting the composition length. Check the first and last rendered frames for unintended leftovers or blank space.

## Media

For new code, prefer `Video` and `Audio` from `@remotion/media` when supported by the installed version. `OffthreadVideo` from `remotion` remains an alternative for specific compatibility or rendering needs. Use `staticFile()` for project assets in `public/`. Probe footage dimensions, duration, frame rate, audio streams, and orientation before setting composition metadata. Test a short segment if the source codec or variable frame rate could cause trouble.

Load fonts through a documented Remotion font loader or a local font with explicit loading. Never depend on an unverified system font. Measure long headlines and captions in the actual frame, including localization or user-provided text.

## Effects and sound

Use a clean cut by default; use `@remotion/transitions` when a transition communicates a change in place, time, or idea. `linearTiming()` is a valid API for transition duration and is not inherently a visual defect. If motion blur is needed, follow the [motion blur guide](https://www.remotion.dev/docs/motion-blur-guide); `Trail` creates echoes rather than realistic camera blur.

Time audio against the rendered action and listen to the output. For word-level captions, follow the current `@remotion/captions` guidance and verify timestamps against speech. Generated captions require human review for names and technical terms.

## Render review

Use Studio for timing and a few rendered stills for layout. Recent CLIs can render several PNG frames with `--frames=0,30,90 --image-format=png`. Watch the final encoded file because stills cannot reveal pacing, audio, transition glitches, or codec problems. For transparent exports, confirm that the composition has no opaque root background and that the chosen image format, codec, and pixel format preserve alpha.
