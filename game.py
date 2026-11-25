import os, sys, json, pygame, random

from typing import NoReturn, Union, Optional

if getattr(sys, "frozen", False): # If file is an executable (.exe)
    DIRECTORY = os.path.dirname(sys.executable)
else:
    DIRECTORY = os.path.dirname(__file__)

THEME_FOULDER_PATH = os.path.join(DIRECTORY, "theme")
CONFIG_FILE_PATH = os.path.join(DIRECTORY, "config.json")

CONFIG = None

SCREEN = None
CLOCK = pygame.time.Clock()

BUTTON_PRESSED = pygame.event.custom_type() # Args: "button": Button
BLOCK_START_DRAGGING = pygame.event.custom_type() # Args: "block": Block
BLOCK_DRAGGING = pygame.event.custom_type() # Args: "block": Block, "pos": tuple[int, int]
BLOCK_STOP_DRAGGING = pygame.event.custom_type() # Args: "block": Block, "pos": tuple[int, int]
DROPDOWN_OPTION_SELECTED = pygame.event.custom_type() # Args: "dropdown": Dropdown, "option": str
DROPDOWN_OPTION_DESELECTED = pygame.event.custom_type() # Args: "dropdown": Dropdown
TEXT_INPUT_OPENED = pygame.event.custom_type() # Args: "text_input": TextInput
TEXT_INPUT_CLOSED = pygame.event.custom_type() # Args: "text_input": TextInput, "text": str

# ----------------------------------------------------------------------------------------

def init() -> None:
    load_configs()
    load_theme()

def load_configs() -> None:
    global CONFIG

    with open(CONFIG_FILE_PATH, "r") as file:
        CONFIG = json.load(file)

def load_theme() -> None:
    global THEME

    theme_file_path = os.path.join(THEME_FOULDER_PATH, f"{CONFIG['theme']}.json")
    with open(theme_file_path, "r") as file:
        THEME = json.load(file)

# ----------------------------------------------------------------------------------------

class ElementBase:
    def __init__(self, rect: pygame.Rect, id: Optional[str]) -> None:
        self.rect = rect.copy()
        self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
        self.id = id if id is not None else "defaults"
        self.state = "normal"
        self.dirty = True

    def set_size(self, width: Optional[float] = None, height: Optional[float] = None) -> None:
        width = self.rect.width if width is None else width
        height = self.rect.height if height is None else height
        if self.rect.size != (width, height):
            self.rect.size = (width, height)
            self.surface = pygame.Surface((width, height), pygame.SRCALPHA)
            self.dirty = True

    def set_pos(self, x: Optional[float] = None, y: Optional[float] = None, attr: str = "center") -> None:
        x = self.rect.x if x is None else x
        y = self.rect.y if y is None else y
        if (x, y) != getattr(self.rect, attr, None):
            setattr(self.rect, attr, (x, y))
            self.dirty = True

    def set_state(self, state: str) -> None:
        if self.state != state:
            self.state = state
            self.dirty = True

    def check_state(self) -> None:
        raise NotImplementedError()

    def draw(self, force: bool = False):
        raise NotImplementedError()

class Element(ElementBase):
    def __init__(self, rect: pygame.Rect, text: Optional[str] = None, id: Optional[str] = None) -> None: 
        super().__init__(rect, id)
        self.text = None
        self.text_surface = None
        self.font = pygame.font.Font(None, self.rect.height)

        if text is not None:
            self.set_text(text)

    def set_text(self, text: Optional[str]) -> None:
        self.text = text
        font_w, font_h = self.font.size(self.text)
        if self.rect.width < font_w:
            self.rect.width = font_w + self.rect.height - font_h

        self.dirty = True

    def set_size(self, width: Optional[float] = None, height: Optional[float] = None) -> None:
        super().set_size(width, height)
        self.font = pygame.font.Font(None, self.rect.height)
        self.set_text(self.text)

    def draw(self, force: bool = False) -> None:
        if self.dirty or force:
            self.surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            rect = pygame.Rect((0, 0), self.rect.size)
            theme = THEME.get(self.id, THEME["defaults"])

            background = theme.get(f"{self.state}_bg", theme["normal_bg"])
            corner_radius = theme.get("corner_radius", -1)
            border_width = theme.get("border_width", 0)

            pygame.draw.rect(self.surface, background, rect, 0, corner_radius)
            if border_width > 0:
                border_color = theme.get(f"{self.state}_border", theme.get("normal_border", None))
                if border_color is not None:
                    pygame.draw.rect(self.surface, border_color, rect, border_width, corner_radius)
            
            if self.text is not None:
                text_color = theme.get(f"{self.state}_text", theme.get("normal_text", None))
                if text_color is not None:
                    self.text_surface = self.font.render(self.text, True, text_color)

            self.dirty = False

        SCREEN.blit(self.surface, self.rect)
        if self.text_surface:
            SCREEN.blit(self.text_surface, self.text_surface.get_rect(center=self.rect.center))
        
class Button(Element):
    def __init__(self, rect: pygame.Rect, text: Optional[str] = None, enabled: bool = True, id: Optional[str] = None) -> None:
        super().__init__(rect, text, id)
        self.enabled = enabled

    def check_state(self) -> None:
        if not self.enabled:
            self.set_state("disabled")
        elif self.rect.collidepoint(pygame.mouse.get_pos()):
            mouse_button_event = pygame.event.get(pygame.MOUSEBUTTONDOWN)
            if mouse_button_event and mouse_button_event[0].button == 1 and pygame.mouse.get_pressed()[0]:
                if not self.state == "clicked":
                    self.set_state("clicked")
                    self.on_press()
            else:
                self.set_state("hovered")
        else:
            self.set_state("normal")

    def on_press(self) -> None:
        pygame.event.post(pygame.event.Event(BUTTON_PRESSED, {"button": self}))

class DropdownOption(Button):
    def __init__(self, dropdown: "Dropdown", rect: pygame.Rect, text: Optional[str] = None) -> None:
        super().__init__(rect, text, True, dropdown.option_id)
        self.dropdown = dropdown

    def on_press(self) -> None:
        if self.dropdown.selected == self.text:
            self.dropdown.selected = None
            pygame.event.post(pygame.event.Event(DROPDOWN_OPTION_DESELECTED, {"dropdown": self.dropdown}))
        else:
            self.dropdown.selected = self.text
            pygame.event.post(pygame.event.Event(DROPDOWN_OPTION_SELECTED, {"dropdown": self.dropdown, "option": self.text}))

class Dropdown(Button):
    def __init__(self, rect: pygame.Rect, text: Optional[str], *options: str, selected: Optional[str] = None, id: Optional[str] = None, option_id: Optional[str] = None) -> None:
        self._text = text
        self.option_id = option_id
        self.selected = selected
        self._options: dict[str, DropdownOption] = {}
        self.opened = False
        self._current_first_idx = 0
        super().__init__(rect, text, True, id)
        self.add_options(*options)
    
    @property
    def options(self) -> list[DropdownOption]:
        return list(self._options.values())[self._current_first_idx:]

    def set_selected(self, option: Union[DropdownOption, str, None]) -> None:
        option = getattr(option, "text", option) # Will only get "text" if option is "DropdownOption"
        if self.selected == option or option is None:
            self.selected = None
        elif option in self._options:
            self.selected = option

    def check_state(self) -> None:
        super().check_state()
        if self.state in ("clicked", "hovered"):
            scroll_event = pygame.event.get(pygame.MOUSEWHEEL)
            if scroll_event:
                if (0 <= self._current_first_idx + scroll_event[0].y < len(self._options)):
                    self._current_first_idx += scroll_event[0].y
                    self.repos_options()

        if self.opened:
            for option in self.options:
                option.check_state()

    def on_press(self) -> None:
        if self.opened:
            self.opened = False
        else:
            self.opened = True

    def add_options(self, *options: str) -> None:
        option_keys = list(self._options.keys())
        bottom_y = self.rect.bottom if len(self._options) == 0 else list(self._options.values())[-1].rect.bottom
        for key in options:
            if key not in option_keys:
                option_keys.append(key)
                
                rect = pygame.Rect(self.rect.left, bottom_y, self.rect.width, self.rect.height)
                self._options[key] = DropdownOption(self, rect, key)
                bottom_y = rect.bottom

        self.dirty = True

    def remove_options(self, *options: str) -> None:
        for key in options:
            if key in self._options:
                if self.selected == key:
                    self.selected = None
                self._options.pop(key)
        self.repos_options()

    def repos_options(self, start_y: Optional[int] = None) -> None:
        y = self.rect.bottom if start_y is None else start_y
        for option in self.options:
            option.rect.topleft = (self.rect.left, y)
            y = option.rect.bottom

        self.dirty = True

    def set_text(self, text: Optional[str]) -> None:
        self._text = text
        if not self.selected:
            super().set_text(text)

    def draw(self, force: bool = False) -> None:
        if self.selected:
            if self.text != self.selected:
                super().set_text(self.selected)
        elif self.text != self._text:
            super().set_text(self._text)

        super().draw()

class TextInput(Button):
    def __init__(self, rect: pygame.Rect, text: Optional[str] = None, start_text: Optional[str] = None, id: Optional[str] = None) -> None:
        self._text = text
        self.input_text = start_text if start_text is not None else ""
        super().__init__(rect, text, True, id)

    def check_state(self) -> None:
        if self.rect.collidepoint(pygame.mouse.get_pos()):
            mouse_button_event = pygame.event.get(pygame.MOUSEBUTTONDOWN)
            if mouse_button_event and mouse_button_event[0].button == 1 and pygame.mouse.get_pressed()[0]:
                if self.state == "clicked":
                    self.close()
                else:
                    self.open()
            elif self.state != "clicked":
                self.set_state("hovered")
                    
        elif self.state != "clicked":
            self.set_state("normal")

        if self.state == "clicked":
            self.handle_events()

    def open(self) -> None:
        self.set_state("clicked")
        pygame.event.get(pygame.KEYDOWN) # Clear previous button presses
        pygame.event.post(pygame.event.Event(TEXT_INPUT_OPENED, {"text_input": self}))

    def close(self) -> None:
        self.set_state("hovered")
        pygame.event.post(pygame.event.Event(TEXT_INPUT_CLOSED, {"text_input": self, "text": self.input_text}))

    def handle_events(self) -> None:
        events = pygame.event.get([pygame.TEXTINPUT, pygame.KEYDOWN])
        for event in events:
            if event.type == pygame.TEXTINPUT:
                self.input_text += event.text
                self.dirty = True
            elif event.type == pygame.KEYDOWN:
                if event.unicode == "\x08": # Backspace
                    self.input_text = self.input_text[:-1]
                    self.dirty = True
                elif event.unicode == "\r": # Enter
                    self.close()

    def set_text(self, text: Optional[str]) -> None:
        super().set_text(text)
        if not self.input_text.endswith(text):
            self._text = text

    def _set_to_input_text(self) -> None:
        text = self.input_text
        while self.font.size(text)[0] > self.rect.width:
            text = text[1:]
        self.set_text(text)

    def reset(self) -> None:
        self.input_text = ""

    def draw(self, force = False) -> None:
        if self.input_text:
            self._set_to_input_text()
        elif self.text != self._text:
            super().set_text(self._text)
        super().draw()

class Block(Element):
    def __init__(self, rect: pygame.Rect, text: Optional[str] = None, id: Optional[str] = None) -> None:
        super().__init__(rect, None, id)
        self.dragging = False

        if text:
            self.rect.width = 0
            self.set_text(text)

    def check_state(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        if self.dragging and pygame.mouse.get_pressed()[0]:
            self.rect.center = mouse_pos
            pygame.event.post(pygame.event.Event(BLOCK_DRAGGING, {"block": self, "pos": self.rect.center}))
        elif self.dragging:
            self.dragging = False
            pygame.event.post(pygame.event.Event(BLOCK_STOP_DRAGGING, {"block": self, "pos": self.rect.center}))
        elif self.rect.collidepoint(mouse_pos):
            if pygame.event.get(pygame.MOUSEBUTTONDOWN):
                if self.state != "clicked":
                    self.set_state("clicked")
                    self.dragging = True
                    pygame.event.post(pygame.event.Event(BLOCK_START_DRAGGING, {"block": self}))
            elif not self.dragging:
                self.set_state("hovered")
        else:
            self.set_state("normal")

class Slot(ElementBase):
    def __init__(self, rect: pygame.Rect, filled: Optional[Block] = None, id: Optional[str] = None) -> None:
        super().__init__(rect, id)
        self.filled = filled
        self.filled_rect = pygame.Rect(rect.topleft, (-1, -1))
        self.scale_factor = 1.2
        self.highlight = None

    @property
    def rendered_rect(self) -> pygame.Rect:
        if self.filled:
            self.filled_rect.height = self.filled.rect.height * self.scale_factor
            self.filled_rect.width = self.filled.rect.width + self.filled_rect.height - self.filled.rect.height
            self.filled_rect.topleft = self.rect.topleft
            return self.filled_rect
        return self.rect

    def set_highlight(self, color) -> None:
        self.highlight = color
        self.dirty = True

    def set_pos(self, x: Optional[float] = None, y: Optional[float] = None, attr: str = "center") -> None:
        super().set_pos(x, y, attr)
        self.filled_rect.center = self.rect.center

    def check_state(self) -> None:
        if self.filled:
            if self.state != "clicked":
                self.set_state("clicked")
        elif self.state != "normal":
            self.set_state("normal")

    def draw(self, force: bool = False) -> None:
        rendered_rect = self.rendered_rect
        if self.dirty or force:
            self.surface = pygame.Surface(rendered_rect.size, pygame.SRCALPHA)
            theme = THEME.get(self.id, THEME["defaults"])
            rect = pygame.Rect((0, 0), rendered_rect.size)

            background = theme.get(f"{self.state}_bg", theme["normal_bg"])
            corner_radius = theme.get("corner_radius", -1)

            if self.highlight and self.state == "clicked":
                background = self.highlight
            
            pygame.draw.rect(self.surface, background, rect, 0, corner_radius)

            self.dirty = False

        SCREEN.blit(self.surface, rendered_rect)

class Menu:
    _instances = {}
    current = None

    @classmethod
    def set(cls, name: str) -> None:
        instance = cls._instances.get(name)
        if not instance:
            for sublcass in cls.__subclasses__():
                if sublcass.__name__ == name:
                    cls._instances[name] = instance = sublcass()
        
        if not instance:
            raise ValueError(f"No such 'Menu' subclass: '{name}'")
        
        cls.current = instance

    def __init__(self) -> None:
        self.elements: dict[str, Element] = {}
        self.dropdowns: list[Dropdown] = []
        self.create()
    
    def create(self) -> None:
        raise NotImplementedError()

    def handle_events(self) -> None:
        pass

    def draw(self) -> None:
        for element in self.elements.values():
            element.check_state()
            element.draw()

        for dropdown in self.dropdowns:
            if dropdown.opened:
                for option in dropdown.options:
                    option.check_state()
                    option.draw()

    def add(self, **elements: Element) -> None:
        for key, element in elements.items():
            self.elements[key] = element

            if isinstance(element, Dropdown):
                self.dropdowns.append(element)

class Start(Menu):
    def create(self) -> None:
        play_btn = Button(pygame.Rect(0, 0, 175, 50), "Spela")
        play_btn.rect.center = (400, 150)

        mode_dropdown = Dropdown(pygame.Rect(0, 0, 150, 35), "Välj Läge", *CONFIG["modes"].keys(), selected=CONFIG["current_mode"])
        mode_dropdown.rect.center = (400, 200)
        mode_dropdown.repos_options()
        
        edit_btn = Button(pygame.Rect(0, 0, 150, 35), "Ändra")
        edit_btn.rect.center = (400, 242)

        add_text_input = TextInput(pygame.Rect(0, 0, 150, 35), "Lägg till")
        add_text_input.rect.center = (400, 284)

        self.add(play=play_btn, mode=mode_dropdown, edit=edit_btn, add=add_text_input)

    def handle_events(self) -> None:
        events = pygame.event.get([BUTTON_PRESSED, DROPDOWN_OPTION_SELECTED, DROPDOWN_OPTION_DESELECTED, TEXT_INPUT_CLOSED])
        for event in events:
            if event.type == BUTTON_PRESSED:
                if event.button == self.elements["play"]:
                    if CONFIG["modes"].get(CONFIG["current_mode"], None):
                        Menu.set("Game")
                elif event.button == self.elements["edit"]:
                    if CONFIG["current_mode"]:
                        Menu.set("Edit")
            elif event.type == DROPDOWN_OPTION_SELECTED:
                if event.dropdown == self.elements["mode"]:
                    CONFIG["current_mode"] = event.option
            elif event.type == DROPDOWN_OPTION_DESELECTED:
                if event.dropdown == self.elements["mode"]:
                    CONFIG["current_mode"] = None
            elif event.type == TEXT_INPUT_CLOSED:
                if event.text and event.text not in CONFIG["modes"]:
                    CONFIG["modes"][event.text] = []
                    CONFIG["current_mode"] = event.text

                    self.dropdowns[0].add_options(event.text)
                    self.dropdowns[0].set_selected(event.text)
                    event.text_input.reset()

class Game(Menu):
    def __init__(self) -> None:
        self.slots: list[Slot] = []
        self.game_specific_elements = []
        self.started = False
        self.sentence = []
        super().__init__()

    def start_new_game(self) -> list[str]:
        sentence = random.choice(CONFIG["modes"][CONFIG["current_mode"]])
        split_char = "|" if "|" in sentence else " "
        split_sentence = sentence.split(split_char)

        if split_sentence != self.sentence:
            self.sentence = [word for word in split_sentence if word and not word.isspace()]
            shuffled = self.sentence.copy()
            random.shuffle(shuffled)

            sep = 10
            
            slot_left = sep
            slot_top = sep
            for _ in shuffled:
                slot = Slot(pygame.Rect(slot_left, slot_top, 50, 25))
                if slot_left + slot.rect.width + sep >= 800:
                    slot_top += slot.rect.height + sep
                    slot_left = sep

                    slot.rect.topleft = (slot_left, slot_top)
                
                slot_left += slot.rect.width + sep

                self.slots.append(slot)
                self.game_specific_elements.append(slot)

            block_left = sep
            block_top = slot.rect.bottom + slot.rect.height + sep * 2
            for word in shuffled:
                if word and not word.isspace():
                    block = Block(pygame.Rect(block_left, block_top, -1, 25), word)
                    
                    if block.rect.right - sep >= 800:
                        block_top += block.rect.height + sep
                        block_left = sep

                        block.rect.topleft = (block_left, block_top)

                    block_left += block.rect.width + sep

                    self.game_specific_elements.append(block)

            self.repos_slots()
        elif len(CONFIG["modes"][CONFIG["current_mode"]]) == 1:
            self.sentence = None
            self.start_new_game()
        else:
            self.start_new_game()
        self.started = True

    def check(self) -> None:
        if all(slot.filled for slot in self.slots):
            win = True

            for idx, slot in enumerate(self.slots):
                if slot.filled.text == self.sentence[idx]:
                    slot.set_highlight(THEME["correct"])
                else:
                    slot.set_highlight(THEME["incorrect"])
                    win = False
            
            if win:
                self.elements["next"].enabled = True
            
    def end_game(self) -> None:
        self.started = False
        self.elements["next"].enabled = False

        self.slots.clear()
        self.game_specific_elements.clear()

    def create(self) -> None:
        btn_w, btn_h = (75, 30)
        back_btn = Button(pygame.Rect(0, 400 - btn_h, btn_w, btn_h), "Tillbaka")
        check_btn = Button(pygame.Rect(800 - btn_w * 2, 400 - btn_h, btn_w, btn_h), "Svara")
        next_btn = Button(pygame.Rect(800 - btn_w, 400 - btn_h, btn_w, btn_h), "Nästa", False)

        self.add(back=back_btn, check=check_btn, next=next_btn)
    
    def repos_slots(self) -> None:
        ex_slot_rect = self.slots[0].rect
        sep = ex_slot_rect.width / 5
    
        start_y = sep
        start_x = sep
        for slot in self.slots:
            rendered_rect = slot.rendered_rect
            if start_x + rendered_rect.width >= 800:
                start_y += rendered_rect.height + sep
                start_x = sep

            slot.rect.topleft = (start_x, start_y)
            if slot.filled:
                slot.filled.rect.center = rendered_rect.center
            start_x += rendered_rect.width + sep

    def handle_events(self) -> None:
        events = pygame.event.get([BLOCK_START_DRAGGING, BLOCK_STOP_DRAGGING, BLOCK_DRAGGING, BUTTON_PRESSED])
        for event in events:
            if event.type == BLOCK_DRAGGING:
                for slot in self.slots:
                    if slot.highlight:
                        slot.set_highlight(None)
                    
                    if slot.rect.collidepoint(event.pos):
                        if all(s.filled != event.block for s in self.slots):
                            if not slot.filled:
                                slot.filled = event.block
                    elif slot.filled == event.block:
                        slot.filled = None
            elif event.type == BUTTON_PRESSED:
                if event.button == self.elements["back"]:
                    Menu.set("Start")
                    self.end_game()
                elif event.button == self.elements["check"]:
                    self.check()
                elif event.button == self.elements["next"]:
                    self.end_game()
                    self.start_new_game()

    def draw(self) -> None:
        if not self.started:
            self.start_new_game()
            
        self.repos_slots()
        dragging = []
        for element in self.game_specific_elements:
            element.check_state()
            if getattr(element, "dragging", None):
                dragging.append(element)
            else:
                element.draw()
        
        for element in dragging:
            element.draw()
        super().draw()

class Edit(Menu):
    def __init__(self) -> None:
        self._text_inputs: list[TextInput] = []
        self._selected_text_input: TextInput = None
        self._last_mode = ""
        super().__init__()

    def create(self) -> None:
        btn_h = 30
        back_btn = Button(pygame.Rect(0, 400 - btn_h, 0, btn_h), "Tillbaka")
        del_btn = Button(pygame.Rect(0, 400 - btn_h * 2, 0, btn_h), "Ta bort", False)
        add_btn = Button(pygame.Rect(0, 400 - btn_h * 3, 0, btn_h), "Lägg till")

        max_width = max(btn.rect.width for btn in (back_btn, del_btn, add_btn))

        for btn in (back_btn, del_btn, add_btn):
            btn.set_size(max_width)

        self.add(back=back_btn, delete=del_btn, add=add_btn)

    def create_text_input(self, text: str) -> None:
        left = self.elements["back"].rect.right
        top = self._text_inputs[-1].rect.bottom if len(self._text_inputs) > 0 else 0
        text_input = TextInput(pygame.Rect(left, top, 800 - left, 25), "", text)
        self._text_inputs.append(text_input)

    def _create_text_inputs(self) -> None:
        self._text_inputs.clear()

        for sentence in CONFIG["modes"][CONFIG["current_mode"]]:
            self.create_text_input(sentence)

    def handle_events(self) -> None:
        if CONFIG["current_mode"] != self._last_mode:
            self._last_mode = CONFIG["current_mode"]
            self._create_text_inputs()
            
            if len(self._text_inputs) == 0:
                self.elements["delete"].enabled = True
            else:
                self.elements["delete"].enabled = False

        events = pygame.event.get([BUTTON_PRESSED, TEXT_INPUT_OPENED, TEXT_INPUT_CLOSED, pygame.MOUSEWHEEL])
        for event in events:
            if event.type == BUTTON_PRESSED:
                if event.button == self.elements["back"]:
                    Menu.set("Start")
                elif event.button == self.elements["add"]:
                    self.create_text_input("")
                    self._text_inputs[-1].open()

                elif event.button == self.elements["delete"]:
                    if len(self._text_inputs) == 0:
                        if self._last_mode == CONFIG["current_mode"]:

                            self._instances["Start"].elements["mode"].remove_options(CONFIG["current_mode"])

                            CONFIG["modes"].pop(CONFIG["current_mode"])
                            CONFIG["current_mode"] = None

                            Menu.set("Start")
                    else:
                        if len(self._text_inputs) - 1 != 0:
                            self.elements["delete"].enabled = False
                        
                        sentences = CONFIG["modes"][CONFIG["current_mode"]]
                        if self._selected_text_input.input_text in sentences:
                            sentences.remove(self._selected_text_input.input_text)

                        if self._selected_text_input:
                            self._text_inputs.remove(self._selected_text_input)
                            self._selected_text_input = None

                            y = 0
                            for text_input in self._text_inputs:
                                text_input.rect.top = y
                                y = text_input.rect.bottom

            elif event.type == TEXT_INPUT_OPENED:
                if event.text_input in self._text_inputs:
                    if self._selected_text_input:
                        self._selected_text_input.close()

                    self._selected_text_input = event.text_input
                    self.elements["delete"].enabled = True
            elif event.type == TEXT_INPUT_CLOSED:
                if event.text_input == self._selected_text_input:
                    self._selected_text_input = None
                    self.elements["delete"].enabled = False

                idx = self._text_inputs.index(event.text_input)
                sentences = CONFIG["modes"][CONFIG["current_mode"]]
                if event.text_input.input_text:
                    if event.text_input.input_text not in sentences:
                        if idx in range(len(sentences)):
                            sentences[idx] = event.text_input.input_text
                        else:
                            sentences.append(event.text_input.input_text)
                elif idx in range(len(sentences)):
                    event.text_input.input_text = sentences[idx]
            elif event.type == pygame.MOUSEWHEEL:
                if self._text_inputs[-1].rect.bottom + event.y >= 400 and self._text_inputs[0].rect.top + event.y <= 0:
                    for text_input in self._text_inputs:
                        text_input.rect.y += event.y

    def draw(self) -> None:
        for text_input in self._text_inputs:
            text_input.check_state()
            text_input.draw()
        return super().draw()

# ----------------------------------------------------------------------------------------

def main() -> NoReturn:
    global SCREEN

    init()
    pygame.init()
    SCREEN = pygame.display.set_mode(CONFIG["size"])
    pygame.display.set_caption(CONFIG["title"])

    fps_font = pygame.font.Font(None, 25)
    fps_cap = CONFIG["fps_cap"]

    Menu.set("Start")

    running = True
    while running:
        SCREEN.fill(THEME["background"])

        if pygame.event.get(pygame.QUIT):
            running = False

        Menu.current.handle_events()
        Menu.current.draw()

        if CONFIG["show_fps"]:
            fps_surface: pygame.Surface = fps_font.render(f"FPS: {int(CLOCK.get_fps())}", True, [0, 0, 0])
            SCREEN.blit(fps_surface, (0, 0))

        pygame.display.update()

        CLOCK.tick(fps_cap)
    
    quit()

def quit(code: int = 0) -> None:
    pygame.quit()

    with open(CONFIG_FILE_PATH, "w") as file:
        json.dump(CONFIG, file, indent=4)
    
    sys.exit(code)

if __name__ == "__main__":
    main()