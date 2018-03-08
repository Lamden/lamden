# -*- coding: utf-8 -*-
#

import sys
import os

sys.path.insert(0, os.path.abspath('../'))

extensions = ['sphinx.ext.autodoc']
source_suffix = '.rst'
master_doc = 'index'
project = u'Cilantro'
copyright = u'Lamden'
exclude_patterns = ['_build']
pygments_style = 'sphinx'
html_theme = 'classic'
autoclass_content = "both"

