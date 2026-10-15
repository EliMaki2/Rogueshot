import pygame
import math

Width = 1000
Height = 625


def setup_ui():
    global screen, Horizontal_Scale, Vertical_Scale
    info = pygame.display.Info()
    screen_width = info.current_w
    screen_height = info.current_h
    window_width = screen_width
    window_height = screen_height
    print(f"Screen Resolution: {screen_width}x{screen_height}")
    window_height = math.ceil(window_height * 0.9)  # Use 90% of the screen height
    window_width = math.ceil(window_width * 0.95)  # Use 95% of the screen width
    screen = pygame.display.set_mode((window_width, window_height))
    Width = 1000
    Height = 625
    Horizontal_Scale = window_width / Width
    Vertical_Scale = window_height / Height
    print(f"Horizontal Scale: {Horizontal_Scale}")
    print(f"Vertical Scale: {Vertical_Scale}")

    # Text Setup
    pygame.font.init()
    font_size = math.ceil(
        40 * Vertical_Scale
    )  # Scale the font size based on the vertical scale
    Fonts.font = pygame.font.SysFont("ocraextended", font_size)
    Fonts.title = pygame.font.SysFont("magneto", round(font_size * 2.5))
    Fonts.bold = pygame.font.SysFont("ocraextended", round(font_size * 0.8))
    Fonts.suble = pygame.font.SysFont("ocraextended", round(font_size / 2))
    Fonts.tiny = pygame.font.SysFont("ocraextended", round(font_size / 4))


# MouseClick utility for UI buttons
def MouseClick(button, mouse_x, mouse_y, mouse_pressed):
    return (
        (button.x <= mouse_x <= button.x + button.width)
        and (button.y <= mouse_y <= button.y + button.height)
        and mouse_pressed
    )


# These will be set by main.py after screen setup
screen = None
Horizontal_Scale = 1
Vertical_Scale = 1


# Color Definitions
class Color:
    MenuLight = (116, 188, 219)
    MenuDark = (28, 87, 112)
    MenuLightSelect = (191, 82, 227)
    MenuDarkSelect = (70, 13, 79)
    MenuText = (250, 103, 40)
    MenuAlert = (190, 180, 50)


# Fonts will be set after pygame.font.init() and scaling
class Fonts:
    font = None
    title = None
    bold = None
    suble = None
    tiny = None


class Button:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


def MakeButton(
    x,
    y,
    width,
    height,
    text,
    text_color=Color.MenuText,
    button_color=Color.MenuLight,
    select_color=Color.MenuLightSelect,
    draw=True,
    Font=None,
    outline=True,
):
    global screen, Horizontal_Scale, Vertical_Scale
    if draw:
        pygame.draw.rect(
            screen,
            button_color,
            (
                x * Horizontal_Scale,
                y * Vertical_Scale,
                width * Horizontal_Scale,
                height * Vertical_Scale,
            ),
        )
        mouse_x, mouse_y = pygame.mouse.get_pos()
        mouse_x = mouse_x / Horizontal_Scale
        mouse_y = mouse_y / Vertical_Scale
        if (x <= mouse_x <= x + width) and (y <= mouse_y <= y + height) and outline:
            pygame.draw.rect(
                screen,
                select_color,
                (
                    x * Horizontal_Scale,
                    y * Vertical_Scale,
                    width * Horizontal_Scale,
                    height * Vertical_Scale,
                ),
                10,
            )
        if Font is None:
            Font = Fonts.font
        text_surface = Font.render(text, True, text_color)
        text_rect = text_surface.get_rect(
            center=(
                (x + width / 2) * Horizontal_Scale,
                (y + height / 2) * Vertical_Scale,
            )
        )
        screen.blit(text_surface, text_rect)
    return Button(x, y, width, height)
