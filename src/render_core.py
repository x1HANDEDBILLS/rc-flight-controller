# render_core.py - background, fonts, helpers

import pygame
import numpy as np

def create_gradient_bg(w, h, c1, c2):
    x = np.linspace(0, 1, w, dtype=np.float32)
    y = np.linspace(0, 1, h, dtype=np.float32)
    xv, yv = np.meshgrid(x, y)
    ratio = np.power((xv + yv) / 2, 1.15)
    r = (c1[0] + (c2[0] - c1[0]) * ratio).astype(np.uint8)
    g = (c1[1] + (c2[1] - c1[1]) * ratio).astype(np.uint8)
    b = (c1[2] + (c2[2] - c1[2]) * ratio).astype(np.uint8)
    arr = np.dstack((r, g, b)).swapaxes(0, 1)
    return pygame.surfarray.make_surface(arr).convert()
