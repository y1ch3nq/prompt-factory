from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yaml


APP_DIR = Path(__file__).parent
HISTORY_PATH = APP_DIR / "outputs" / "history.csv"
JUDGE_LINES_HISTORY_PATH = APP_DIR / "outputs" / "judge_lines.csv"
SAMPLE_BATCH_PATH = APP_DIR / "examples" / "sample_batch.csv"

OUTPUT_TYPE_TO_TEMPLATE = {
    "Grok Image Prompt": "grok_image",
    "Grok Video Prompt": "grok_video",
    "Judge Reaction Prompt": "judge_reaction",
    "Audience Reaction Prompt": "audience_reaction",
    "Voiceover Prompt": "voiceover",
    "Suno Music Prompt": "suno_music",
    "Social Caption Prompt": "social_caption",
}

OUTPUT_ALIASES = {
    "social caption / title / hashtag prompt": "Social Caption Prompt",
    "social caption/title/hashtag prompt": "Social Caption Prompt",
    "social caption prompt": "Social Caption Prompt",
}

BATCH_COLUMNS = [
    "output_type",
    "character",
    "scene_type",
    "emotion",
    "camera_angle",
    "camera_movement",
    "dialogue_mode",
    "action",
    "dialogue_line",
    "aspect_ratio",
    "extra_notes",
    "negative_constraints",
]

HISTORY_COLUMNS = [
    "timestamp",
    "output_type",
    "character",
    "scene_type",
    "emotion",
    "camera_angle",
    "camera_movement",
    "dialogue_mode",
    "action",
    "aspect_ratio",
    "generated_prompt",
]

JUDGE_LINE_COLUMNS = [
    "timestamp",
    "judge",
    "line_type",
    "language",
    "line",
]

THREE_JUDGES_MODE = "Three Judges Same Emotion, Different Reactions"

TEXT_FIELD_KEYS = [
    "reference_notes",
    "dialogue_line",
    "extra_scene_details",
    "negative_constraints",
    "custom_character_description",
    "custom_scene_description",
    "custom_emotion",
    "custom_camera_angle",
    "custom_camera_movement",
    "custom_action",
    "custom_mood",
    "custom_aspect_ratio",
    "voiceover_duration",
    "voiceover_type",
    "suno_style",
    "voice_gender",
    "voice_style",
    "custom_voice_description",
]

SELECT_DEFAULTS = {
    "output_type": "Grok Video Prompt",
    "character": "Contestant",
    "scene_type": "contestant close-up",
    "emotion": "moved and tearful",
    "camera_angle": "frontal close-up",
    "camera_movement": "subtle slow push-in",
    "dialogue_mode": "no dialogue",
    "action": "wiping tears",
    "mood": "cinematic",
    "aspect_ratio_choice": "9:16 vertical short-form video",
    "voice_gender": "Female voice",
    "voice_style": "warm televised host style",
}

VOICE_GENDER_OPTIONS = [
    "Female voice",
    "Male voice",
    "Androgynous voice",
    "Custom voice",
]

VOICE_STYLE_OPTIONS = [
    "warm televised host style",
    "serious documentary style",
    "suspenseful reality show style",
    "emotional inner monologue style",
    "high-energy announcement style",
    "custom voice style",
]


class SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


@st.cache_data(show_spinner=False)
def load_yaml(relative_path: str) -> dict[str, Any]:
    path = APP_DIR / relative_path
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (FileNotFoundError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def preset_items(filename: str) -> list[dict[str, Any]]:
    data = load_yaml(f"presets/{filename}")
    items = data.get("items", [])
    return items if isinstance(items, list) else []


def option_names(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("name", "")).strip() for item in items if item.get("name")]


def item_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    wanted = clean_value(name).lower()
    for item in items:
        if clean_value(item.get("name")).lower() == wanted:
            return item
    return {}


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def single_line(value: str) -> str:
    return re.sub(r"\s+", " ", clean_value(value))


def is_custom_choice(value: str) -> bool:
    return clean_value(value).lower().startswith("custom")


def get_global_rules() -> dict[str, Any]:
    return load_yaml("presets/global_rules.yaml")


def get_template(output_type: str) -> dict[str, Any]:
    template_key = OUTPUT_TYPE_TO_TEMPLATE[output_type]
    data = load_yaml(f"templates/{template_key}.yaml")
    template = data.get("template", {})
    if isinstance(template, dict) and template:
        return template
    return {
        "name": output_type,
        "visual": output_type not in {"Voiceover Prompt", "Suno Music Prompt", "Social Caption Prompt"},
        "rules": [],
        "body": "{scene_details}\n\n{important_rules}",
    }


def normalize_output_type(raw: Any) -> str:
    value = clean_value(raw)
    if value in OUTPUT_TYPE_TO_TEMPLATE:
        return value
    lower = value.lower()
    if lower in OUTPUT_ALIASES:
        return OUTPUT_ALIASES[lower]
    for label in OUTPUT_TYPE_TO_TEMPLATE:
        if label.lower() == lower:
            return label
    return SELECT_DEFAULTS["output_type"]


def template_key_for(output_type: str) -> str:
    return OUTPUT_TYPE_TO_TEMPLATE[normalize_output_type(output_type)]


def is_visual_output(output_type: str) -> bool:
    return bool(get_template(normalize_output_type(output_type)).get("visual", False))


def scene_options(global_rules: dict[str, Any]) -> list[str]:
    scenes = (
        global_rules.get("reality_music_competition", {})
        .get("scenes", [])
    )
    return scenes or [
        "judge reaction",
        "audience reaction",
        "stage transition",
        "backstage hallway",
        "contestant close-up",
        "host introduction",
        "performance aftermath",
        "social caption",
        "custom scene",
    ]


def mood_options(global_rules: dict[str, Any]) -> list[str]:
    moods = (
        global_rules.get("reality_music_competition", {})
        .get("common_mood_words", [])
    )
    return moods or [
        "cinematic",
        "emotional",
        "suspenseful",
        "polished broadcast",
        "dramatic reality show",
        "warm and touching",
        "tense and awkward",
        "custom mood",
    ]


def ensure_default_state() -> None:
    for key, value in SELECT_DEFAULTS.items():
        st.session_state.setdefault(key, value)
    for key in TEXT_FIELD_KEYS:
        st.session_state.setdefault(key, "")
    st.session_state.setdefault("special_three_judges", False)
    st.session_state.setdefault("generated_prompt", "")
    st.session_state.setdefault("generated_context", {})
    st.session_state.setdefault("judge_line_index", 0)
    st.session_state.setdefault("judge_line_last_criteria", "")
    st.session_state.setdefault("kept_judge_lines", [])


def output_field_config(output_type: str) -> dict[str, bool]:
    template_key = template_key_for(output_type)
    config = {
        "character": True,
        "scene": True,
        "emotion": True,
        "camera_angle": False,
        "camera_movement": False,
        "dialogue_mode": False,
        "action": False,
        "mood": True,
        "aspect": False,
        "reference_notes": False,
        "dialogue_line": False,
        "voice_controls": False,
        "voiceover_controls": False,
        "suno_style": False,
        "custom_character": True,
        "custom_camera": False,
        "custom_action": False,
    }

    if template_key == "grok_video":
        config.update(
            camera_angle=True,
            camera_movement=True,
            dialogue_mode=True,
            action=True,
            aspect=True,
            reference_notes=True,
            dialogue_line=True,
            custom_camera=True,
            custom_action=True,
        )
    elif template_key == "grok_image":
        config.update(
            camera_angle=True,
            action=True,
            aspect=True,
            reference_notes=True,
            custom_camera=True,
            custom_action=True,
        )
    elif template_key in {"judge_reaction", "audience_reaction"}:
        config.update(
            camera_angle=True,
            camera_movement=True,
            dialogue_mode=True,
            action=True,
            aspect=True,
            reference_notes=True,
            dialogue_line=True,
            custom_camera=True,
            custom_action=True,
        )
    elif template_key == "voiceover":
        config.update(
            character=False,
            scene=False,
            emotion=False,
            camera_angle=False,
            camera_movement=False,
            dialogue_mode=False,
            action=False,
            mood=False,
            aspect=False,
            reference_notes=False,
            dialogue_line=True,
            voice_controls=True,
            voiceover_controls=True,
            custom_character=False,
        )
    elif template_key == "suno_music":
        config.update(
            character=False,
            camera_angle=False,
            camera_movement=False,
            dialogue_mode=False,
            action=False,
            aspect=False,
            reference_notes=False,
            suno_style=True,
            custom_character=False,
        )
    elif template_key == "social_caption":
        config.update(
            camera_angle=False,
            camera_movement=False,
            dialogue_mode=False,
            action=False,
            aspect=False,
            reference_notes=False,
        )

    return config


def selectbox(label: str, options: list[str], key: str, default: str, container=st) -> str:
    if not options:
        options = [default]
    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = default if default in options else options[0]
    return container.selectbox(label, options, key=key)


def resolve_description(
    items: list[dict[str, Any]],
    selected: str,
    custom_value: str = "",
    fallback: str = "",
) -> str:
    selected = clean_value(selected)
    item = item_by_name(items, selected)
    if is_custom_choice(selected):
        return single_line(custom_value) or clean_value(item.get("description")) or fallback or selected
    return clean_value(item.get("description")) or selected or fallback


def resolve_scene(scene_type: str, custom_scene: str, extra_notes: str) -> tuple[str, str]:
    scene_name = single_line(custom_scene) if is_custom_choice(scene_type) else clean_value(scene_type)
    scene_name = scene_name or "music competition scene"
    notes = single_line(extra_notes)
    if notes:
        return scene_name, f"{scene_name}. Extra scene details: {notes}"
    return scene_name, scene_name


def aspect_lookup(raw: Any, aspect_items: list[dict[str, Any]]) -> tuple[str, str]:
    value = clean_value(raw)
    if not value:
        return "", ""

    lower = value.lower()
    for item in aspect_items:
        names = {
            clean_value(item.get("name")).lower(),
            clean_value(item.get("phrase")).lower(),
            clean_value(item.get("visual_phrase")).lower(),
        }
        if lower in names:
            phrase = clean_value(item.get("visual_phrase")) or clean_value(item.get("phrase"))
            return phrase, clean_value(item.get("name")) or value

    return value, value


def resolve_aspect_ratio(
    choice: str,
    custom_value: str,
    aspect_items: list[dict[str, Any]],
) -> tuple[str, str]:
    if clean_value(choice).lower() == "custom":
        custom = single_line(custom_value) or "custom aspect ratio"
        return custom, custom
    return aspect_lookup(choice, aspect_items)


def default_aspect(aspect_items: list[dict[str, Any]]) -> tuple[str, str]:
    return aspect_lookup(SELECT_DEFAULTS["aspect_ratio_choice"], aspect_items)


def resolve_batch_aspect(
    row_value: Any,
    default_phrase: str,
    default_label: str,
    aspect_items: list[dict[str, Any]],
) -> tuple[str, str]:
    value = clean_value(row_value)
    if not value:
        return default_phrase, default_label
    return aspect_lookup(value, aspect_items)


def build_dialogue_rule(dialogue_mode: str, dialogue_line: str, global_rules: dict[str, Any]) -> str:
    mode = clean_value(dialogue_mode)
    lower = mode.lower()
    line = single_line(dialogue_line)
    single_speaker_rule = clean_value(global_rules.get("single_speaker_rule"))

    if lower in {"silent reaction", "no dialogue"}:
        return "No dialogue, no lip sync, no subtitles, no text."
    if lower == "only main character speaks":
        if line:
            return f'Only the main character says: "{line}". {single_speaker_rule}'
        return f"Only the main character speaks. {single_speaker_rule}"
    if lower == "one line of dialogue":
        if line:
            return f'One concise line of dialogue from the main character only: "{line}". {single_speaker_rule}'
        return f"One concise line of dialogue from the main character only. {single_speaker_rule}"
    if lower == "voiceover only":
        if line:
            return f'Voiceover only: "{line}". Visible characters remain silent and do not lip sync.'
        return "Voiceover only. Visible characters remain silent and do not lip sync."
    if lower == "no background voices":
        return "No background voices or crowd chatter. Keep the moment visually readable."
    if lower == "custom dialogue rule":
        return line or "Use the custom dialogue rule; keep speech controlled and clearly assigned."
    return mode or "No dialogue."


def emotion_polarity(emotion: str, emotion_items: list[dict[str, Any]]) -> str:
    item = item_by_name(emotion_items, emotion)
    polarity = clean_value(item.get("polarity"))
    if polarity:
        return polarity
    lower = clean_value(emotion).lower()
    if any(word in lower for word in ["awkward", "confused", "shocked", "disappointed", "tense"]):
        return "negative"
    if any(word in lower for word in ["happy", "moved", "impressed", "admiration", "touching"]):
        return "positive"
    return "neutral"


def build_judge_personality_block(
    character: str,
    emotion: str,
    emotion_description: str,
    special_three_judges: bool,
    global_rules: dict[str, Any],
    emotion_items: list[dict[str, Any]],
) -> str:
    personalities = global_rules.get("judge_personalities", {})
    if not isinstance(personalities, dict):
        return "Use distinct, believable judge body language based on the selected emotion."

    polarity = emotion_polarity(emotion, emotion_items)
    reaction_key = "negative" if polarity == "negative" else "positive"

    def line_for(judge_name: str) -> str:
        rules = personalities.get(judge_name, {})
        traits = clean_value(rules.get("traits"))
        reactions = rules.get(reaction_key, [])
        reaction_text = ", ".join(clean_value(item) for item in reactions[:4])
        return f"{judge_name}: {traits}; show {reaction_text}."

    judge_names = ["Purple female judge", "Black male judge", "Colorful male judge"]
    if special_three_judges:
        lines = [f"Overall emotion: {emotion_description}."]
        lines.extend(line_for(name) for name in judge_names)
        return "\n".join(lines)

    if character in personalities:
        return line_for(character)
    if character == "Three judges":
        return "\n".join(line_for(name) for name in judge_names)
    return "Use the selected character's personality to make the reaction specific, believable, and not generic."


def dedupe_rules(rules: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for rule in rules:
        cleaned = single_line(rule).rstrip(".")
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def build_important_rules(
    output_type: str,
    template: dict[str, Any],
    data: dict[str, Any],
    global_rules: dict[str, Any],
) -> str:
    rules: list[str] = []
    if is_visual_output(output_type):
        rules.extend(global_rules.get("common_visual_constraints", []))
    rules.extend(template.get("rules", []))

    if clean_value(data.get("reference_notes")):
        rules.extend(global_rules.get("reference_image_constraints", []))

    dialogue_mode = clean_value(data.get("dialogue_mode")).lower()
    if dialogue_mode in {"silent reaction", "no dialogue"} and template_key_for(output_type) in {
        "judge_reaction",
        "audience_reaction",
    }:
        rules.extend(global_rules.get("silent_reaction_constraints", []))

    if dialogue_mode in {"only main character speaks", "one line of dialogue"}:
        rules.append(clean_value(global_rules.get("single_speaker_rule")))

    negative = single_line(data.get("negative_constraints", ""))
    if negative:
        rules.append(f"User negative constraints: {negative}")

    return "; ".join(dedupe_rules(rules)) + "."


def clean_prompt(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    output: list[str] = []
    previous_blank = False
    for line in lines:
        if not line.strip():
            if output and not previous_blank:
                output.append("")
            previous_blank = True
            continue
        output.append(line)
        previous_blank = False
    return "\n".join(output).strip()


def render_template(template: dict[str, Any], context: dict[str, Any]) -> str:
    body = clean_value(template.get("body")) or "{scene_details}\n\n{important_rules}"
    rendered = body.format_map(SafeDict(context))
    return clean_prompt(rendered)


def shorten_suno_prompt(prompt: str) -> str:
    if len(prompt) <= 1000:
        return prompt
    return prompt[:997].rstrip() + "..."


def build_context(data: dict[str, Any]) -> dict[str, Any]:
    global_rules = get_global_rules()
    character_items = preset_items("characters.yaml")
    emotion_items = preset_items("emotions.yaml")
    camera_angle_items = preset_items("camera_angles.yaml")
    camera_movement_items = preset_items("camera_movements.yaml")
    action_items = preset_items("actions.yaml")
    aspect_items = preset_items("aspect_ratios.yaml")

    output_type = normalize_output_type(data.get("output_type"))
    template = get_template(output_type)
    template_key = template_key_for(output_type)
    visual = bool(template.get("visual", False))

    character = clean_value(data.get("character")) or SELECT_DEFAULTS["character"]
    special_three_judges = bool(data.get("special_three_judges")) or character == THREE_JUDGES_MODE
    if special_three_judges:
        character = THREE_JUDGES_MODE

    custom_character = clean_value(data.get("custom_character_description"))
    character_description = resolve_description(
        character_items,
        character,
        custom_character,
        "A realistic music competition character.",
    )
    if special_three_judges:
        character_description = resolve_description(character_items, THREE_JUDGES_MODE)

    if output_type == "Voiceover Prompt":
        voice_gender = clean_value(data.get("voice_gender")) or SELECT_DEFAULTS["voice_gender"]
        voice_style = clean_value(data.get("voice_style")) or SELECT_DEFAULTS["voice_style"]
        custom_voice = clean_value(data.get("custom_voice_description"))
        if is_custom_choice(voice_gender) or is_custom_choice(voice_style):
            character_description = custom_voice or f"{voice_gender}, {voice_style}"
        else:
            character_description = f"{voice_gender}, {voice_style}"

    scene_name, scene_details = resolve_scene(
        clean_value(data.get("scene_type")) or SELECT_DEFAULTS["scene_type"],
        clean_value(data.get("custom_scene_description")),
        clean_value(data.get("extra_scene_details") or data.get("extra_notes")),
    )

    if output_type == "Voiceover Prompt" and clean_value(data.get("voiceover_type")):
        scene_name = clean_value(data.get("voiceover_type"))
        scene_details = scene_name

    emotion = clean_value(data.get("emotion")) or SELECT_DEFAULTS["emotion"]
    emotion_description = resolve_description(
        emotion_items,
        emotion,
        clean_value(data.get("custom_emotion")),
        emotion,
    )

    action = clean_value(data.get("action")) or SELECT_DEFAULTS["action"]
    action_description = resolve_description(
        action_items,
        action,
        clean_value(data.get("custom_action")),
        action,
    )
    action_description = f"{action_description}; emotion: {emotion_description}"

    camera_angle = clean_value(data.get("camera_angle")) or SELECT_DEFAULTS["camera_angle"]
    camera_movement = clean_value(data.get("camera_movement")) or SELECT_DEFAULTS["camera_movement"]

    if special_three_judges and output_type == "Judge Reaction Prompt":
        camera_angle = "three-judge frontal shot"
        camera_movement = "completely static camera"
        data = {**data, "dialogue_mode": "silent reaction"}

    camera_angle_description = resolve_description(
        camera_angle_items,
        camera_angle,
        clean_value(data.get("custom_camera_angle")),
        camera_angle,
    )
    camera_movement_description = resolve_description(
        camera_movement_items,
        camera_movement,
        clean_value(data.get("custom_camera_movement")),
        camera_movement,
    )
    camera_requirement = clean_value(global_rules.get("default_camera_requirement"))
    camera_instruction = (
        f"{camera_angle_description}. {camera_movement_description}. "
        f"The camera remains {camera_requirement}."
    )

    mood = clean_value(data.get("mood")) or SELECT_DEFAULTS["mood"]
    mood_description = single_line(data.get("custom_mood")) if is_custom_choice(mood) else mood
    mood_description = mood_description or SELECT_DEFAULTS["mood"]

    if visual:
        aspect_phrase = clean_value(data.get("aspect_ratio_text"))
        aspect_label = clean_value(data.get("aspect_ratio_label"))
        if not aspect_phrase:
            aspect_phrase, aspect_label = default_aspect(aspect_items)
    else:
        aspect_phrase, aspect_label = "", ""

    reference_notes = clean_value(data.get("reference_notes"))
    reference_line = clean_value(global_rules.get("reference_image_rule")) if reference_notes else ""
    reference_notes_line = f"Reference notes: {single_line(reference_notes)}" if reference_notes else ""

    dialogue_rule = build_dialogue_rule(
        clean_value(data.get("dialogue_mode")) or SELECT_DEFAULTS["dialogue_mode"],
        clean_value(data.get("dialogue_line")),
        global_rules,
    )

    judge_personality_block = build_judge_personality_block(
        character,
        emotion,
        emotion_description,
        special_three_judges,
        global_rules,
        emotion_items,
    )

    audience_rules = " ".join(clean_value(rule) for rule in global_rules.get("audience_rules", []))
    voiceover_duration = (
        single_line(data.get("voiceover_duration"))
        or clean_value(global_rules.get("voiceover", {}).get("default_duration"))
        or "6 seconds"
    )
    dialogue_or_intent = single_line(data.get("dialogue_line")) or scene_details
    negative_constraints_line = (
        f"Additional negative constraints: {single_line(data.get('negative_constraints'))}"
        if single_line(data.get("negative_constraints"))
        else ""
    )
    suno_style = single_line(data.get("suno_style")) or "cinematic suspense trailer underscore"

    context = {
        "output_type": output_type,
        "template_key": template_key,
        "visual": visual,
        "character": character,
        "character_description": character_description,
        "scene_type": scene_name,
        "scene_description": scene_name,
        "scene_details": scene_details,
        "emotion": emotion,
        "emotion_description": emotion_description,
        "action": action,
        "action_description": action_description,
        "camera_angle": camera_angle,
        "camera_angle_description": camera_angle_description,
        "camera_movement": camera_movement,
        "camera_movement_description": camera_movement_description,
        "camera_instruction": camera_instruction,
        "dialogue_mode": clean_value(data.get("dialogue_mode")) or SELECT_DEFAULTS["dialogue_mode"],
        "dialogue_rule": dialogue_rule,
        "mood": mood,
        "mood_description": mood_description,
        "aspect_ratio_text": aspect_phrase,
        "aspect_ratio_label": aspect_label,
        "reference_line": reference_line,
        "reference_notes_line": reference_notes_line,
        "important_rules": build_important_rules(output_type, template, data, global_rules),
        "judge_personality_block": judge_personality_block,
        "audience_rules": audience_rules,
        "voiceover_duration": voiceover_duration,
        "dialogue_or_intent": dialogue_or_intent,
        "negative_constraints_line": negative_constraints_line,
        "suno_style": suno_style,
        "special_three_judges": special_three_judges,
        "voice_gender": clean_value(data.get("voice_gender")) or SELECT_DEFAULTS["voice_gender"],
        "voice_style": clean_value(data.get("voice_style")) or SELECT_DEFAULTS["voice_style"],
    }
    return context


def generate_prompt(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    output_type = normalize_output_type(data.get("output_type"))
    template = get_template(output_type)
    context = build_context(data)
    prompt = render_template(template, context)
    if template_key_for(output_type) == "suno_music":
        prompt = shorten_suno_prompt(prompt)
    return prompt, context


def history_row(context: dict[str, Any], prompt: str) -> dict[str, str]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "output_type": clean_value(context.get("output_type")),
        "character": clean_value(context.get("character")),
        "scene_type": clean_value(context.get("scene_type")),
        "emotion": clean_value(context.get("emotion")),
        "camera_angle": clean_value(context.get("camera_angle")),
        "camera_movement": clean_value(context.get("camera_movement")),
        "dialogue_mode": clean_value(context.get("dialogue_mode")),
        "action": clean_value(context.get("action")),
        "aspect_ratio": clean_value(context.get("aspect_ratio_label")),
        "generated_prompt": prompt,
    }


def append_history(rows: list[dict[str, str]]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not HISTORY_PATH.exists() or HISTORY_PATH.stat().st_size == 0
    with HISTORY_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_COLUMNS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in HISTORY_COLUMNS})


def load_history() -> pd.DataFrame:
    if not HISTORY_PATH.exists() or HISTORY_PATH.stat().st_size == 0:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    try:
        return pd.read_csv(HISTORY_PATH)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame(columns=HISTORY_COLUMNS)


def judge_line_preset() -> dict[str, Any]:
    data = load_yaml("presets/judge_lines.yaml")
    judges = data.get("judges", {})
    return judges if isinstance(judges, dict) else {}


def judge_line_judges() -> list[str]:
    judges = list(judge_line_preset().keys())
    return judges or ["Purple female judge", "Black male judge", "Colorful male judge"]


def judge_line_types(judge: str) -> list[str]:
    judge_data = judge_line_preset().get(judge, {})
    lines = judge_data.get("lines", {}) if isinstance(judge_data, dict) else {}
    return list(lines.keys()) or ["Praise", "Critique / Roast"]


def judge_line_languages(judge: str, line_type: str) -> list[str]:
    judge_data = judge_line_preset().get(judge, {})
    lines = judge_data.get("lines", {}) if isinstance(judge_data, dict) else {}
    language_map = lines.get(line_type, {}) if isinstance(lines, dict) else {}
    return list(language_map.keys()) or ["English"]


def generated_judge_line(judge: str, line_type: str, language: str, index: int) -> str:
    judge_data = judge_line_preset().get(judge, {})
    lines = judge_data.get("lines", {}) if isinstance(judge_data, dict) else {}
    language_map = lines.get(line_type, {}) if isinstance(lines, dict) else {}
    choices = language_map.get(language, []) if isinstance(language_map, dict) else []
    if not choices:
        return "No local line presets found for this selection."
    return clean_value(choices[index % len(choices)])


def judge_line_history_row(judge: str, line_type: str, language: str, line: str) -> dict[str, str]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "judge": judge,
        "line_type": line_type,
        "language": language,
        "line": line,
    }


def append_judge_line_history(row: dict[str, str]) -> None:
    JUDGE_LINES_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not JUDGE_LINES_HISTORY_PATH.exists() or JUDGE_LINES_HISTORY_PATH.stat().st_size == 0
    with JUDGE_LINES_HISTORY_PATH.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=JUDGE_LINE_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in JUDGE_LINE_COLUMNS})


def load_judge_line_history() -> pd.DataFrame:
    if not JUDGE_LINES_HISTORY_PATH.exists() or JUDGE_LINES_HISTORY_PATH.stat().st_size == 0:
        return pd.DataFrame(columns=JUDGE_LINE_COLUMNS)
    try:
        history = pd.read_csv(JUDGE_LINES_HISTORY_PATH)
        for column in JUDGE_LINE_COLUMNS:
            if column not in history.columns:
                history[column] = ""
        return history[JUDGE_LINE_COLUMNS]
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame(columns=JUDGE_LINE_COLUMNS)


def current_input_data() -> dict[str, Any]:
    aspect_items = preset_items("aspect_ratios.yaml")
    aspect_phrase, aspect_label = "", ""
    output_type = normalize_output_type(st.session_state.get("output_type"))
    if is_visual_output(output_type):
        aspect_phrase, aspect_label = resolve_aspect_ratio(
            st.session_state.get("aspect_ratio_choice", SELECT_DEFAULTS["aspect_ratio_choice"]),
            st.session_state.get("custom_aspect_ratio", ""),
            aspect_items,
        )

    return {
        "output_type": output_type,
        "character": st.session_state.get("character"),
        "scene_type": st.session_state.get("scene_type"),
        "emotion": st.session_state.get("emotion"),
        "camera_angle": st.session_state.get("camera_angle"),
        "camera_movement": st.session_state.get("camera_movement"),
        "dialogue_mode": st.session_state.get("dialogue_mode"),
        "action": st.session_state.get("action"),
        "mood": st.session_state.get("mood"),
        "aspect_ratio_text": aspect_phrase,
        "aspect_ratio_label": aspect_label,
        "reference_notes": st.session_state.get("reference_notes", ""),
        "dialogue_line": st.session_state.get("dialogue_line", ""),
        "extra_scene_details": st.session_state.get("extra_scene_details", ""),
        "negative_constraints": st.session_state.get("negative_constraints", ""),
        "custom_character_description": st.session_state.get("custom_character_description", ""),
        "custom_scene_description": st.session_state.get("custom_scene_description", ""),
        "custom_emotion": st.session_state.get("custom_emotion", ""),
        "custom_camera_angle": st.session_state.get("custom_camera_angle", ""),
        "custom_camera_movement": st.session_state.get("custom_camera_movement", ""),
        "custom_action": st.session_state.get("custom_action", ""),
        "custom_mood": st.session_state.get("custom_mood", ""),
        "voiceover_duration": st.session_state.get("voiceover_duration", ""),
        "voiceover_type": st.session_state.get("voiceover_type", ""),
        "suno_style": st.session_state.get("suno_style", ""),
        "voice_gender": st.session_state.get("voice_gender", SELECT_DEFAULTS["voice_gender"]),
        "voice_style": st.session_state.get("voice_style", SELECT_DEFAULTS["voice_style"]),
        "custom_voice_description": st.session_state.get("custom_voice_description", ""),
        "special_three_judges": st.session_state.get("special_three_judges", False),
    }


def clear_single_fields() -> None:
    for key in TEXT_FIELD_KEYS:
        st.session_state[key] = ""
    for key, value in SELECT_DEFAULTS.items():
        st.session_state[key] = value
    st.session_state["special_three_judges"] = False
    st.session_state["generated_prompt"] = ""
    st.session_state["generated_context"] = {}


def render_copy_button(text: str, label: str = "Copy Output") -> None:
    disabled = "disabled" if not text else ""
    payload = json.dumps(text)
    components.html(
        f"""
        <button id="copy-output" {disabled}
          style="width: 100%; padding: 0.65rem 0.85rem; border-radius: 0.45rem;
          border: 1px solid #c9ced6; background: #ffffff; cursor: pointer;
          font-weight: 600;">{label}</button>
        <script>
        const button = document.getElementById("copy-output");
        const text = {payload};
        button?.addEventListener("click", async () => {{
          await navigator.clipboard.writeText(text);
          button.textContent = "Copied";
          setTimeout(() => button.textContent = "{label}", 1300);
        }});
        </script>
        """,
        height=48,
    )


def render_metadata(context: dict[str, Any]) -> None:
    if not context:
        return
    camera = clean_value(context.get("camera_angle"))
    movement = clean_value(context.get("camera_movement"))
    if movement:
        camera = f"{camera} / {movement}" if camera else movement
    rows = [
        ("Output Type", context.get("output_type")),
        ("Character", context.get("character")),
        ("Emotion", context.get("emotion")),
        ("Camera", camera),
        ("Aspect Ratio", context.get("aspect_ratio_label") or "N/A"),
        ("Dialogue Mode", context.get("dialogue_mode")),
    ]
    metadata = pd.DataFrame(
        [{"Field": label, "Value": clean_value(value)} for label, value in rows]
    )
    st.dataframe(metadata, hide_index=True, use_container_width=True)


def read_batch_dataframe(uploaded_file: Any, pasted_csv: str) -> pd.DataFrame | None:
    try:
        if uploaded_file is not None:
            return pd.read_csv(uploaded_file)
        if clean_value(pasted_csv):
            return pd.read_csv(io.StringIO(pasted_csv))
    except Exception as exc:  # Streamlit should show the user the parse problem.
        st.error(f"Could not read CSV: {exc}")
        return None
    return None


def ensure_batch_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for column in BATCH_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = ""
    return cleaned[BATCH_COLUMNS]


def batch_row_data(
    row: pd.Series,
    default_data: dict[str, Any],
    default_aspect_phrase: str,
    default_aspect_label: str,
) -> dict[str, Any]:
    aspect_items = preset_items("aspect_ratios.yaml")
    output_type = normalize_output_type(row.get("output_type") or default_data.get("output_type"))
    if is_visual_output(output_type):
        aspect_phrase, aspect_label = resolve_batch_aspect(
            row.get("aspect_ratio"),
            default_aspect_phrase,
            default_aspect_label,
            aspect_items,
        )
    else:
        aspect_phrase, aspect_label = "", ""

    return {
        **default_data,
        "output_type": output_type,
        "character": clean_value(row.get("character")) or default_data.get("character"),
        "scene_type": clean_value(row.get("scene_type")) or default_data.get("scene_type"),
        "emotion": clean_value(row.get("emotion")) or default_data.get("emotion"),
        "camera_angle": clean_value(row.get("camera_angle")) or default_data.get("camera_angle"),
        "camera_movement": clean_value(row.get("camera_movement")) or default_data.get("camera_movement"),
        "dialogue_mode": clean_value(row.get("dialogue_mode")) or default_data.get("dialogue_mode"),
        "action": clean_value(row.get("action")) or default_data.get("action"),
        "dialogue_line": clean_value(row.get("dialogue_line")),
        "extra_scene_details": clean_value(row.get("extra_notes")),
        "negative_constraints": clean_value(row.get("negative_constraints")),
        "aspect_ratio_text": aspect_phrase,
        "aspect_ratio_label": aspect_label,
        "special_three_judges": clean_value(row.get("character")) == THREE_JUDGES_MODE,
    }


def generate_batch(df: pd.DataFrame, default_data: dict[str, Any]) -> pd.DataFrame:
    aspect_items = preset_items("aspect_ratios.yaml")
    default_aspect_phrase = clean_value(default_data.get("aspect_ratio_text"))
    default_aspect_label = clean_value(default_data.get("aspect_ratio_label"))
    if not default_aspect_phrase:
        default_aspect_phrase, default_aspect_label = default_aspect(aspect_items)

    records: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        data = batch_row_data(row, default_data, default_aspect_phrase, default_aspect_label)
        prompt, context = generate_prompt(data)
        records.append(
            {
                "row": index + 1,
                "output_type": context["output_type"],
                "character": context["character"],
                "scene_type": context["scene_type"],
                "emotion": context["emotion"],
                "camera_angle": context["camera_angle"],
                "camera_movement": context["camera_movement"],
                "dialogue_mode": context["dialogue_mode"],
                "action": context["action"],
                "aspect_ratio": context["aspect_ratio_label"],
                "generated_prompt": prompt,
            }
        )
    return pd.DataFrame(records)


def markdown_export(results: pd.DataFrame) -> str:
    parts = ["# Prompt Factory Batch Export"]
    for _, row in results.iterrows():
        title = f"{row.get('row')}. {row.get('output_type')} - {row.get('character')}"
        parts.append(f"\n## {title}")
        parts.append(
            "Metadata: "
            f"scene={row.get('scene_type')}; "
            f"emotion={row.get('emotion')}; "
            f"camera={row.get('camera_angle')} / {row.get('camera_movement')}; "
            f"aspect_ratio={row.get('aspect_ratio') or 'N/A'}"
        )
        parts.append("```text")
        parts.append(clean_value(row.get("generated_prompt")))
        parts.append("```")
    return "\n".join(parts).strip() + "\n"


def render_workflow_controls() -> None:
    global_rules = get_global_rules()
    characters = option_names(preset_items("characters.yaml"))
    emotions = option_names(preset_items("emotions.yaml"))
    camera_angles = option_names(preset_items("camera_angles.yaml"))
    camera_movements = option_names(preset_items("camera_movements.yaml"))
    dialogue_modes = option_names(preset_items("dialogue_modes.yaml"))
    actions = option_names(preset_items("actions.yaml"))
    aspects = option_names(preset_items("aspect_ratios.yaml"))

    st.subheader("Select")
    selectbox("Output Type", list(OUTPUT_TYPE_TO_TEMPLATE.keys()), "output_type", SELECT_DEFAULTS["output_type"])
    output_type = normalize_output_type(st.session_state.get("output_type"))
    config = output_field_config(output_type)

    select_cols = st.columns(3)
    col_index = 0

    def next_col():
        nonlocal col_index
        column = select_cols[col_index % len(select_cols)]
        col_index += 1
        return column

    if config["voice_controls"]:
        with next_col():
            selectbox("Voice Gender", VOICE_GENDER_OPTIONS, "voice_gender", SELECT_DEFAULTS["voice_gender"])
        with next_col():
            selectbox("Voice Style", VOICE_STYLE_OPTIONS, "voice_style", SELECT_DEFAULTS["voice_style"])

    if config["character"]:
        with next_col():
            selectbox("Character", characters, "character", SELECT_DEFAULTS["character"])
    if config["scene"]:
        with next_col():
            selectbox("Scene Type", scene_options(global_rules), "scene_type", SELECT_DEFAULTS["scene_type"])
    if config["emotion"]:
        with next_col():
            selectbox("Emotion", emotions, "emotion", SELECT_DEFAULTS["emotion"])
    if config["action"]:
        with next_col():
            selectbox("Action / Body Language", actions, "action", SELECT_DEFAULTS["action"])
    if config["mood"]:
        with next_col():
            selectbox("Mood / Style", mood_options(global_rules), "mood", SELECT_DEFAULTS["mood"])
    if config["camera_angle"]:
        with next_col():
            selectbox("Camera Angle", camera_angles, "camera_angle", SELECT_DEFAULTS["camera_angle"])
    if config["camera_movement"]:
        with next_col():
            selectbox("Camera Movement", camera_movements, "camera_movement", "subtle slow push-in")
    if config["dialogue_mode"]:
        with next_col():
            selectbox("Dialogue Mode", dialogue_modes, "dialogue_mode", SELECT_DEFAULTS["dialogue_mode"])

    if is_visual_output(output_type):
        aspect_col, custom_col = st.columns([1, 1])
        with aspect_col:
            selectbox("Aspect Ratio", aspects, "aspect_ratio_choice", SELECT_DEFAULTS["aspect_ratio_choice"])
        with custom_col:
            if st.session_state.get("aspect_ratio_choice") == "Custom":
                st.text_input(
                    "Custom Aspect Ratio",
                    key="custom_aspect_ratio",
                    placeholder="3:4, 21:9, 2560x423",
                )

    if output_type == "Judge Reaction Prompt":
        if "special_three_judges" not in st.session_state:
            st.session_state["special_three_judges"] = (
                st.session_state.get("character") == THREE_JUDGES_MODE
            )
        st.checkbox(
            "Three Judges Same Emotion, Different Reactions",
            key="special_three_judges",
        )

    render_workflow_notes(output_type, global_rules)


def render_workflow_notes(output_type: str, global_rules: dict[str, Any]) -> None:
    config = output_field_config(output_type)
    st.subheader("Further Notes")
    note_col_a, note_col_b = st.columns(2)
    with note_col_a:
        if config["reference_notes"]:
            st.text_area("Uploaded image/reference notes", key="reference_notes", height=110)
        if config["dialogue_line"]:
            label = "Voiceover line / intent" if output_type == "Voiceover Prompt" else "Specific dialogue line"
            st.text_input(label, key="dialogue_line")
    with note_col_b:
        note_label = "Extra voiceover context" if output_type == "Voiceover Prompt" else "Extra scene details"
        st.text_area(note_label, key="extra_scene_details", height=110)
        st.text_area("Negative constraints", key="negative_constraints", height=90)

    if output_type == "Voiceover Prompt":
        voiceover_types = global_rules.get("voiceover", {}).get("types", [])
        voice_col, duration_col = st.columns(2)
        with voice_col:
            if voiceover_types:
                if st.session_state.get("voiceover_type") not in voiceover_types:
                    st.session_state["voiceover_type"] = voiceover_types[0]
                st.selectbox("Voiceover Type", voiceover_types, key="voiceover_type")
        with duration_col:
            st.text_input("Voiceover Duration", key="voiceover_duration", placeholder="6 seconds")

    if output_type == "Suno Music Prompt":
        suno_styles = global_rules.get("suno", {}).get("styles", [])
        if suno_styles:
            if st.session_state.get("suno_style") not in suno_styles:
                st.session_state["suno_style"] = suno_styles[0]
            st.selectbox("Suno Music Style", suno_styles, key="suno_style")

    with st.expander("Custom Overrides", expanded=False):
        if config["voice_controls"]:
            st.text_area("Custom voice description", key="custom_voice_description", height=80)
        if config["custom_character"]:
            st.text_area("Custom character description", key="custom_character_description", height=80)
        if config["scene"]:
            st.text_input("Custom scene description", key="custom_scene_description")
        if config["emotion"]:
            st.text_input("Custom emotion", key="custom_emotion")
        if config["custom_camera"]:
            st.text_input("Custom camera angle", key="custom_camera_angle")
            st.text_input("Custom camera movement", key="custom_camera_movement")
        if config["custom_action"]:
            st.text_input("Custom action", key="custom_action")
        if config["mood"]:
            st.text_input("Custom mood", key="custom_mood")


def render_single_prompt_tab(text_only_checked: bool) -> None:
    render_workflow_controls()

    st.subheader("Generate")
    col_generate, col_clear = st.columns([1, 1])
    with col_generate:
        generate_clicked = st.button(
            "Generate Prompt",
            type="primary",
            disabled=not text_only_checked,
            use_container_width=True,
        )
    with col_clear:
        st.button("Clear Fields", on_click=clear_single_fields, use_container_width=True)

    if generate_clicked:
        prompt, context = generate_prompt(current_input_data())
        st.session_state["generated_prompt"] = prompt
        st.session_state["generated_context"] = context

    prompt = st.session_state.get("generated_prompt", "")
    context = st.session_state.get("generated_context", {})

    render_metadata(context)
    st.text_area("Generated Prompt", value=prompt, height=420)

    col_copy, col_save = st.columns([1, 1])
    with col_copy:
        render_copy_button(prompt)
    with col_save:
        if st.button("Save to History", disabled=not bool(prompt), use_container_width=True):
            append_history([history_row(context, prompt)])
            st.success("Saved to outputs/history.csv")


def render_judge_lines_tab() -> None:
    st.subheader("Judge Line Generator")

    judges = judge_line_judges()
    line_col_a, line_col_b, line_col_c = st.columns(3)
    with line_col_a:
        judge = selectbox("Judge", judges, "judge_line_judge", judges[0])
    with line_col_b:
        types = judge_line_types(judge)
        line_type = selectbox("Line Type", types, "judge_line_type", types[0])
    with line_col_c:
        languages = judge_line_languages(judge, line_type)
        language = selectbox("Language", languages, "judge_line_language", languages[0])

    criteria = f"{judge}|{line_type}|{language}"
    if st.session_state.get("judge_line_last_criteria") != criteria:
        st.session_state["judge_line_index"] = 0
        st.session_state["judge_line_last_criteria"] = criteria

    refresh_col, keep_col, use_col = st.columns(3)
    with refresh_col:
        if st.button("Refresh Line", type="primary", use_container_width=True):
            st.session_state["judge_line_index"] += 1

    line = generated_judge_line(
        judge,
        line_type,
        language,
        int(st.session_state.get("judge_line_index", 0)),
    )
    st.text_area("Generated Judge Line", value=line, height=110)

    with keep_col:
        if st.button("Keep Selected Line", use_container_width=True):
            row = judge_line_history_row(judge, line_type, language, line)
            st.session_state["kept_judge_lines"] = [row] + st.session_state.get("kept_judge_lines", [])
            append_judge_line_history(row)
            st.success("Kept in outputs/judge_lines.csv")
    with use_col:
        if st.button("Use in Single Prompt", use_container_width=True):
            st.session_state["dialogue_line"] = line
            st.session_state["dialogue_mode"] = "one line of dialogue"
            st.success("Added to Single Prompt dialogue line.")

    kept_rows = st.session_state.get("kept_judge_lines", [])
    saved_history = load_judge_line_history()

    st.subheader("Selected Lines")
    if kept_rows:
        st.dataframe(pd.DataFrame(kept_rows), hide_index=True, use_container_width=True, height=220)
    elif not saved_history.empty:
        st.dataframe(saved_history.tail(10).iloc[::-1], hide_index=True, use_container_width=True, height=220)
    else:
        st.dataframe(pd.DataFrame(columns=JUDGE_LINE_COLUMNS), hide_index=True, use_container_width=True)

    if not saved_history.empty:
        st.download_button(
            "Download Selected Lines CSV",
            data=saved_history.to_csv(index=False).encode("utf-8"),
            file_name="judge_lines.csv",
            mime="text/csv",
        )


def render_batch_tab(text_only_checked: bool) -> None:
    uploaded_file = st.file_uploader("CSV upload", type=["csv"])
    pasted_csv = st.text_area("Paste CSV", height=140)

    source_df = read_batch_dataframe(uploaded_file, pasted_csv)
    if source_df is not None:
        st.session_state["batch_source_df"] = source_df
    if source_df is None and SAMPLE_BATCH_PATH.exists():
        if st.button("Load Sample CSV"):
            source_df = pd.read_csv(SAMPLE_BATCH_PATH)
            st.session_state["batch_source_df"] = source_df
    if source_df is None and isinstance(st.session_state.get("batch_source_df"), pd.DataFrame):
        source_df = st.session_state["batch_source_df"]

    if source_df is None:
        st.dataframe(pd.DataFrame(columns=BATCH_COLUMNS), hide_index=True, use_container_width=True)
        return

    preview = ensure_batch_columns(source_df)
    edited = st.data_editor(preview, num_rows="dynamic", use_container_width=True, height=260)

    if st.button("Generate All", type="primary", disabled=not text_only_checked):
        st.session_state["batch_results"] = generate_batch(edited, current_input_data())

    results = st.session_state.get("batch_results")
    if isinstance(results, pd.DataFrame) and not results.empty:
        st.dataframe(results, hide_index=True, use_container_width=True, height=320)
        csv_bytes = results.to_csv(index=False).encode("utf-8")
        markdown_text = markdown_export(results)

        col_csv, col_md, col_save = st.columns(3)
        with col_csv:
            st.download_button(
                "Export CSV",
                data=csv_bytes,
                file_name="prompt_factory_batch.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_md:
            st.download_button(
                "Export Markdown",
                data=markdown_text,
                file_name="prompt_factory_batch.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_save:
            if st.button("Save Batch to History", use_container_width=True):
                rows = []
                for _, row in results.iterrows():
                    context = {
                        "output_type": row.get("output_type"),
                        "character": row.get("character"),
                        "scene_type": row.get("scene_type"),
                        "emotion": row.get("emotion"),
                        "camera_angle": row.get("camera_angle"),
                        "camera_movement": row.get("camera_movement"),
                        "dialogue_mode": row.get("dialogue_mode"),
                        "action": row.get("action"),
                        "aspect_ratio_label": row.get("aspect_ratio"),
                    }
                    rows.append(history_row(context, clean_value(row.get("generated_prompt"))))
                append_history(rows)
                st.success("Batch saved to outputs/history.csv")

        st.text_area("Markdown Export Preview", value=markdown_text, height=260)


def render_history_tab() -> None:
    history = load_history()
    judge_line_history = load_judge_line_history()
    st.subheader("Prompt History")
    st.dataframe(history, hide_index=True, use_container_width=True, height=420)
    if not history.empty:
        st.download_button(
            "Download History CSV",
            data=history.to_csv(index=False).encode("utf-8"),
            file_name="history.csv",
            mime="text/csv",
        )
    st.subheader("Judge Line History")
    st.dataframe(judge_line_history, hide_index=True, use_container_width=True, height=260)
    if not judge_line_history.empty:
        st.download_button(
            "Download Judge Lines CSV",
            data=judge_line_history.to_csv(index=False).encode("utf-8"),
            file_name="judge_lines.csv",
            mime="text/csv",
        )


def main() -> None:
    st.set_page_config(
        page_title="Prompt Factory",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            display: none;
        }
        div[data-testid="stSidebarCollapsedControl"] {
            display: none;
        }
        .block-container {
            max-width: 1040px;
            padding-left: 2rem;
            padding-right: 2rem;
        }
        div[data-testid="stCheckbox"] label p {
            font-weight: 800;
            font-size: 1.03rem;
        }
        textarea {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    ensure_default_state()

    st.title("Prompt Factory")
    text_only_checked = st.checkbox("TEXT OUTPUT ONLY — DO NOT GENERATE IMAGE", value=True)
    if not text_only_checked:
        st.warning("Re-check the text-only control to generate prompts.")

    single_tab, judge_lines_tab, batch_tab, history_tab = st.tabs(
        ["Single Prompt", "Judge Lines", "Batch Mode", "History"]
    )
    with single_tab:
        render_single_prompt_tab(text_only_checked)
    with judge_lines_tab:
        render_judge_lines_tab()
    with batch_tab:
        render_batch_tab(text_only_checked)
    with history_tab:
        render_history_tab()


if __name__ == "__main__":
    main()
