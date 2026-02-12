import pygame
import numpy as np

def create_gradient_bg(width, height, color_dark, color_light, add_dither=True):
    x = np.linspace(0, 1, width, dtype=np.float32)
    y = np.linspace(0, 1, height, dtype=np.float32)
    xv, yv = np.meshgrid(x, y)
    base_ratio = (xv + yv) / np.sqrt(2)
    ratio = 1 - np.power(base_ratio, 1.0)
    r = (color_light[0] + (color_dark[0] - color_light[0]) * ratio).astype(np.float32)
    g = (color_light[1] + (color_dark[1] - color_light[1]) * ratio).astype(np.float32)
    b = (color_light[2] + (color_dark[2] - color_light[2]) * ratio).astype(np.float32)
    arr = np.dstack((r, g, b))
    noise = np.random.normal(0, 1.0, arr.shape)
    arr += noise
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    surface = pygame.surfarray.make_surface(arr.swapaxes(0, 1)).convert()
    return surface