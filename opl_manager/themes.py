"""Application palettes; UGM is the default, Azul preserves the original look."""
from string import Template

DEFAULT_THEME = 'ugm'
THEMES = {'blue': 'Azul', 'green': 'Verde', 'red': 'Rojo',
          'ugm': 'UGM', 'classic': 'Clásico estilo Windows'}

BLUE = dict(
    text='#e6efff', background='#080e20', sidebar='#070e21', card='#0e1a33',
    border_soft='#1a2945', border='#294366', muted='#90a5c7', strong='#d8edff',
    accent_light='#64c8ff', accent='#286ce2', accent_hover='#3988ff',
    cover='#070d1b', button='#162b4c', hover='#234775', pressed='#10213c',
    disabled_text='#7386a3', disabled='#111e33', selected='#18345c',
    input='#0a152c', selection='#1f4370', selection_text='#ffffff',
    menu='#12213b', menubar='#0a1327', header='#11213b', alternate='#111e34',
    scrollbar='#324c73', tooltip='#163257', success='#6ed8c4', warning='#efbe84',
    gradient='#142b53', gradient_end='#090d1c', glow='#2367c0',
    tower='#5aa1ff', sparkle='#8cc5ff', mark='#b5dcff')
PALETTES = {
    'blue': BLUE,
    'green': dict(BLUE,
        text='#e7f5ec', background='#081710', sidebar='#091c14', card='#10291e',
        border_soft='#1d3a2b', border='#2e6047', muted='#a1c5af', strong='#e1ffec',
        accent_light='#82edac', accent='#207747', accent_hover='#2a9259',
        cover='#07130c', button='#1a3c2a', hover='#28543d', pressed='#102b1d',
        disabled_text='#82998a', disabled='#13271b', selected='#205038',
        input='#0a2015', selection='#286244', menu='#132f20', menubar='#0b2016',
        header='#153523', alternate='#142f21', scrollbar='#39694c', tooltip='#204b33',
        gradient='#17452d', gradient_end='#08150e', glow='#27a467',
        tower='#66d99b', sparkle='#b0f7cd', mark='#baffd1'),
    'red': dict(BLUE,
        text='#ffecec', background='#1a090e', sidebar='#200c12', card='#30131b',
        border_soft='#48212b', border='#73404c', muted='#cda7af', strong='#ffe7eb',
        accent_light='#ff9eae', accent='#b52f49', accent_hover='#d03a58',
        cover='#15070b', button='#4a1e2a', hover='#642a3a', pressed='#34151e',
        disabled_text='#a6858e', disabled='#2b161d', selected='#5c2333',
        input='#240d15', selection='#7c2e44', menu='#351620', menubar='#250d15',
        header='#421b28', alternate='#381620', scrollbar='#804653', tooltip='#542333',
        gradient='#532035', gradient_end='#190a10', glow='#d83e61',
        tower='#ff7b91', sparkle='#ffc1cd', mark='#ffc0cc'),
    # Ubuntu-inspired violet and orange, on dark graphite gaming panels.
    'ugm': dict(BLUE,
        text='#f4eef9', background='#130f1d', sidebar='#17121f', card='#211a2d',
        border_soft='#342940', border='#544162', muted='#b9a9c9', strong='#fff0e9',
        accent_light='#ffad80', accent='#ad421a', accent_hover='#c44f22',
        cover='#100c17', button='#35263f', hover='#513047', pressed='#251b30',
        disabled_text='#9788a5', disabled='#251e30', selected='#4e2b3a',
        input='#191222', selection='#743c4e', menu='#271d32', menubar='#1a1323',
        header='#2c2039', alternate='#2a2035', scrollbar='#675071', tooltip='#3c2949',
        success='#a6e3b2', warning='#ffbe8b', gradient='#3b2055', gradient_end='#160e1e',
        glow='#e95420', tower='#b36bdf', sparkle='#ffd1b8', mark='#ffad80'),
    'classic': dict(BLUE,
        text='#000000', background='#d4d0c8', sidebar='#d4d0c8', card='#ece9d8',
        border_soft='#a09c94', border='#808080', muted='#454545', strong='#000000',
        accent_light='#000080', accent='#000080', accent_hover='#003399',
        cover='#ffffff', button='#d4d0c8', hover='#e5e3dc', pressed='#bcb8b0',
        disabled_text='#686868', disabled='#c8c4bc', selected='#b9c9df',
        input='#ffffff', selection='#000080', menu='#ece9d8', menubar='#d4d0c8',
        header='#d4d0c8', alternate='#f0f0f0', scrollbar='#a09c94', tooltip='#ffffe1',
        success='#146638', warning='#8a3c08', gradient='#d4d0c8', gradient_end='#d4d0c8',
        glow='#d4d0c8', tower='#d4d0c8', sparkle='#d4d0c8', mark='#000080'),
}


def theme_key(value):
    return value if isinstance(value, str) and value in THEMES else DEFAULT_THEME


STYLE = Template(r"""
* { font-family: "Ubuntu", "Noto Sans", sans-serif; font-size: 13px; color: $text; }
QMainWindow, QDialog { background: $background; }
QFrame#sidebar { background: $sidebar; border-right: 1px solid $border_soft; }
QFrame#card { background: $card; border: 1px solid $border; border-radius: 17px; }
QFrame#stat { background: $card; border: 1px solid $border; border-radius: 14px; }
QLabel { background: transparent; border: none; }
QLabel#muted { color: $muted; }
QLabel#eyebrow { color: $accent_light; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#heading { font-size: 30px; font-weight: 700; letter-spacing: -1px; }
QLabel#number { font-size: 29px; font-weight: 700; color: $strong; }
QLabel#detailTitle { font-size: 20px; font-weight: 700; }
QLabel#cover { background: $cover; border: 1px solid $border; border-radius: 10px; color: $muted; }
QPushButton { background: $button; border: 1px solid $border; border-radius: 10px; padding: 10px 14px; font-weight: 500; }
QPushButton:hover { background: $hover; border-color: $accent_light; }
QPushButton:pressed { background: $pressed; }
QPushButton:disabled { color: $disabled_text; border-color: $border_soft; background: $disabled; }
QPushButton#primary { background: $accent; border: 1px solid $accent_light; color: $selection_text; font-weight: 700; }
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#nav { text-align: left; border: none; background: transparent; padding: 12px 16px; color: $muted; }
QPushButton#nav:checked { background: $selected; color: $strong; border: 1px solid $border; }
QPushButton#nav:hover { background: $hover; color: $strong; }
QLineEdit,QComboBox,QPlainTextEdit { background: $input; border: 1px solid $border; border-radius: 9px; padding: 9px 12px; selection-background-color: $selection; }
QLineEdit:focus,QPlainTextEdit:focus { border-color: $accent_light; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background: $menu; selection-background-color: $selection; }
QTableWidget { background: transparent; alternate-background-color: $alternate; border: none; gridline-color: $border_soft; outline: none; }
QTableWidget::item { border-bottom: 1px solid $border_soft; padding: 8px; }
QTableWidget::item:selected { background: $selection; color: $selection_text; }
QHeaderView::section { background: $header; border: none; border-bottom: 1px solid $border; padding: 12px 8px; color: $muted; font-size: 11px; font-weight: 700; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 3px; }
QScrollBar::handle:vertical { background: $scrollbar; border-radius: 3px; min-height: 30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { background: $input; height: 9px; }
QScrollBar::handle:horizontal { background: $scrollbar; min-width: 30px; }
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal { width: 0px; }
QProgressBar { background: $input; border: none; border-radius: 4px; height: 6px; color: $strong; text-align: center; }
QProgressBar::chunk { background: $accent_light; border-radius: 4px; }
QSplitter::handle { background: transparent; width: 12px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QMenuBar { background: $menubar; color: $text; }
QMenuBar::item:selected,QMenu::item:selected { background: $selection; }
QMenu { background: $menu; border: 1px solid $border; padding: 6px; }
QMenu::item { padding: 9px 26px; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid $border; border-radius: 4px; background: $input; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent_light; }
QTabWidget::pane { border: 1px solid $border; background: $input; }
QTabBar::tab { background: $button; border: 1px solid $border; padding: 10px 12px; color: $muted; }
QTabBar::tab:selected { background: $selection; color: $selection_text; }
QToolTip { background: $tooltip; color: $text; border: 1px solid $border; padding: 6px; }

QMenu::indicator { width: 12px; height: 12px; border: 1px solid $border; border-radius: 6px; background: $input; }
QMenu::indicator:checked { background: $accent_light; border-color: $accent_light; }
QMenu::item:disabled { color: $disabled_text; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }
QSpinBox,QDoubleSpinBox,QTextEdit,QListView { background: $input; color: $text; border: 1px solid $border; selection-background-color: $selection; selection-color: $selection_text; }
QRadioButton { spacing: 9px; }
QRadioButton::indicator:checked { background: $accent; border: 1px solid $accent_light; border-radius: 7px; width: 13px; height: 13px; }
QPushButton:focus { border-color: $accent_light; }
""")

CLASSIC_STYLE = """
* { font-family: "Tahoma", "DejaVu Sans", sans-serif; }
QFrame#card,QFrame#stat,QLabel#cover,QPushButton,QLineEdit,QComboBox,QPlainTextEdit,
QCheckBox::indicator,QTabBar::tab,QProgressBar,QProgressBar::chunk { border-radius: 0px; }
QFrame#card,QFrame#stat { border: 2px groove #ffffff; }
QPushButton { border: 2px outset #f0f0f0; }
QPushButton:pressed { border: 2px inset #f0f0f0; }
QPushButton#primary { border: 2px outset #8080c0; }
QPushButton#nav:checked { border: 1px inset #808080; }
QLineEdit,QComboBox,QPlainTextEdit,QLabel#cover { border: 2px inset #f0f0f0; }
QMenu::item:selected,QMenuBar::item:selected { color: white; background: #000080; }
QHeaderView::section { border: 1px outset #f0f0f0; }
QCheckBox::indicator:checked { background: #000080; border-color: #000080; }
"""


def stylesheet(key):
    key = theme_key(key)
    return STYLE.substitute(PALETTES[key]) + (CLASSIC_STYLE if key == 'classic' else '')
