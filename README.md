# Prompt Factory

Prompt Factory is a local Streamlit web app for generating production-ready text prompts for short-form reality music competition workflows. It is form-based, deterministic, template-driven, and designed for copy/paste into tools such as Grok, Suno, or other AI production tools.

## What This App Does

- Generates text prompts from editable YAML templates and presets.
- Supports Grok image prompts, Grok video prompts, judge reactions, audience reactions, voiceovers, Suno music prompts, and social caption prompts.
- Includes a local Judge Lines workflow for cycling through praise or critique lines by judge personality.
- Lets you choose characters, emotions, camera rules, dialogue rules, actions, moods, and visual aspect ratios.
- Supports single prompt generation and CSV batch generation.
- Saves generated prompt history locally to `outputs/history.csv`.

## What This App Does Not Do

- It does not generate images.
- It does not generate videos.
- It does not generate music.
- It does not call any external AI API.
- It is not a chatbot.
- It is not a ChatGPT skill.

## Install Dependencies

From this folder:

```bash
pip install -r requirements.txt
```

## Run Locally

```bash
streamlit run app.py
```

Streamlit will print a local URL, usually:

```text
http://localhost:8501
```

## Edit YAML Presets

Templates live in `templates/`:

- `grok_image.yaml`
- `grok_video.yaml`
- `judge_reaction.yaml`
- `audience_reaction.yaml`
- `voiceover.yaml`
- `suno_music.yaml`
- `social_caption.yaml`

Presets live in `presets/`:

- `characters.yaml`
- `emotions.yaml`
- `camera_angles.yaml`
- `camera_movements.yaml`
- `dialogue_modes.yaml`
- `actions.yaml`
- `aspect_ratios.yaml`
- `global_rules.yaml`

Edit YAML values, save the file, then refresh the Streamlit app. The Python loader handles missing YAML files gracefully, but keeping the files valid YAML is recommended.

## Single Prompt Mode

1. Check `TEXT OUTPUT ONLY — DO NOT GENERATE IMAGE`.
2. Choose an output type in the sidebar.
3. Select character, scene, emotion, camera angle, camera movement, dialogue mode, action, mood, and aspect ratio when relevant.
4. Fill any optional free-text fields.
5. Click `Generate Prompt`.
6. Copy the generated text or save it to local history.

The single prompt form uses output-type hierarchy. For example, `Voiceover Prompt` only shows voice gender, voice style, voiceover type, duration, and relevant notes instead of camera/action/aspect-ratio controls.

## Judge Lines Mode

1. Open the `Judge Lines` tab.
2. Choose the judge, line type, and language.
3. Click `Refresh Line` until you find a line you like.
4. Click `Keep Selected Line` to save it locally to `outputs/judge_lines.csv`.
5. Click `Use in Single Prompt` to place that line into the single prompt dialogue field.

## Batch Mode

Use `examples/sample_batch.csv` or provide a CSV with these columns:

```text
output_type, character, scene_type, emotion, camera_angle, camera_movement, dialogue_mode, action, dialogue_line, aspect_ratio, extra_notes, negative_constraints
```

Batch mode supports:

- CSV upload
- CSV paste
- Editable preview table
- Generate All
- Export CSV
- Export Markdown
- Save batch results to `outputs/history.csv`

If a row has an `aspect_ratio`, that value is used. If it is blank, the selected UI default aspect ratio is used for visual prompt types.

## Example Vertical Video Prompt

```text
Create a realistic vertical 9:16 cinematic video clip for contestant close-up.

Character:
Talented music competition contestant under bright stage pressure, emotionally focused and camera-ready.

Action:
wiping tears gently while trying to stay composed; emotion: visibly touched, emotional eyes, restrained tears, sincere warmth

Camera:
frontal close-up focused on facial expression and emotional detail. a subtle slow push-in that gently increases emotional focus. The camera remains stable, smooth, no shaking, no sudden movement.

Dialogue:
No dialogue, no lip sync, no subtitles, no text.
```

## Example Horizontal Video Prompt

```text
Create a realistic horizontal 16:9 cinematic video clip for judge reaction.

Character:
Gentle, emotionally sensitive, warm female judge in a polished purple outfit.

Camera:
frontal close-up focused on facial expression and emotional detail. the camera remains completely locked off and stable. The camera remains stable, smooth, no shaking, no sudden movement.
```

## Example YouTube Banner Prompt

```text
Create a 2560x423 YouTube banner-style cinematic image for host introduction.

Character:
Polished televised competition host with confident posture, clean styling, warm authority, and stage-ready delivery.

Composition:
wide stage shot showing the performance space, lights, and atmosphere. Realistic broadcast lighting, polished composition, clear character consistency.
```

## Example Judge Reaction Prompt

```text
Create a realistic vertical 9:16 cinematic judge reaction video clip for a high-end televised music competition.

Judge Reaction Logic:
Overall emotion: visibly touched, emotional eyes, restrained tears, sincere warmth.
Purple female judge: gentle, emotionally sensitive, warm, easily moved; show gentle smile, emotional eyes, hand over chest, soft nodding.
Black male judge: strict, serious, sharp, controlled, hard to impress; show controlled nod, serious approval, slight eyebrow lift, restrained respect.
Colorful male judge: chill, playful, expressive, slightly chaotic; show relaxed applause, amused smile, impressed side glance, chill approval.
```

## Example Suno Music Prompt

```text
Create polished music for a reality music competition scene.
Style: emotional piano cinematic underscore.
Mood: warm and touching; emotion: visibly touched, emotional eyes, restrained tears, sincere warmth.
Instrumentation: cinematic piano, restrained strings, soft pulses, tasteful broadcast percussion unless the notes specify otherwise.
Pacing: edit-friendly, clear build, no messy transitions.
Constraints: no vocals unless explicitly requested, no lyrics unless explicitly requested, commercial high-end broadcast sound.
```
