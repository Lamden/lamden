import os
from pathlib import Path
import logging, coloredlogs
from logging.config import fileConfig

path = os.path.dirname(Path(__file__).parents[0])
os.chdir(path)
path += "/conf"
loggerIniFile = path + "/cilantro_logger.ini"
fileConfig(loggerIniFile)


# LVL_STYLES = coloredlogs.DEFAULT_LEVEL_STYLES
# LVL_STYLES['critical']['background'] = 'blue'


lvl_styles = coloredlogs.DEFAULT_LEVEL_STYLES
COLORS = ('blue', 'cyan', 'green', 'magenta', 'red', 'yellow', 'white')
LVLS = ('debug', 'info', 'warning', 'error', 'critical')



def get_logger(name: str, bg_color=None, auto_bg_val=None):
    def apply_bg_color(lvls, color):
        for lvl in lvls:
            lvl_styles[lvl]['background'] = color
            lvl_styles[lvl]['color'] = 'black'
            # if ('color' in lvl_styles[lvl]) and (lvl_styles[lvl]['color'] == color):
            #     lvl_styles[lvl]['color'] = 'white'

    if auto_bg_val is not None:
        assert bg_color is None, "Cannot set both bg_color and auto_bg_val (must be one or the other)"
        color = COLORS[auto_bg_val % len(COLORS)]
        apply_bg_color(LVLS, color)

    if bg_color is not None:
        assert auto_bg_val is None, "Cannot set both bg_color and auto_bg_val (must be one or the other)"
        apply_bg_color(LVLS, bg_color)

    log = logging.getLogger(name)
    coloredlogs.install(level='DEBUG', logger=log, level_styles=lvl_styles)

    return log
