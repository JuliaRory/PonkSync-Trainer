import json
from string import Template

def load_palette(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_qss(theme_path, palette_path):
    palette = load_palette(palette_path)
    with open(theme_path, "r", encoding="utf-8") as f:
        qss_template = Template(f.read())
    return qss_template.substitute(
        app_bg=palette["app_bg"],
        border=palette["border"],
        text=palette["text"],

        panel_left_background=palette["panel_left"]["background"],
        panel_left_text=palette["panel_left"]["text"],
        panel_left_button=palette["panel_left"]["button"],
        panel_left_button_hover=palette["panel_left"]["button_hover"],
        panel_left_accent=palette["panel_left"]["accent"],
        
        splitter_background = palette["splitter"]["background"],
        splitter_border = palette["splitter"]["border"],

        tep_plot_background = palette["tep_plot"]["background"],
        mep_plot_background = palette["emg_plot"]["background"]
    )