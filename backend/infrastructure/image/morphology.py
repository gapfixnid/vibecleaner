"""Morphological operations for the image toolkit."""

from __future__ import annotations
import cv2
import numpy as np


MORPH_RECT = cv2.MORPH_RECT
MORPH_CROSS = cv2.MORPH_CROSS
MORPH_ELLIPSE = cv2.MORPH_ELLIPSE

MORPH_OPEN = 'open'
MORPH_CLOSE = 'close'
MORPH_GRADIENT = 'gradient'
MORPH_TOPHAT = 'tophat'
MORPH_BLACKHAT = 'blackhat'


def dilate(mask: np.ndarray, kernel: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Apply dilation morphological operation to a mask.
    
    Args:
        mask: Input mask
        kernel: a 2D numpy array kernel
        iterations: Number of iterations
    """
    return cv2.dilate(mask, kernel.astype(np.uint8), iterations=iterations)


def erode(mask: np.ndarray, kernel: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Apply erosion morphological operation to a mask.
    
    Args:
        mask: Input mask
        kernel: a 2D numpy array kernel
        iterations: Number of iterations
    """
    return cv2.erode(mask, kernel.astype(np.uint8), iterations=iterations)


def morphology_ex(image: np.ndarray, op: str, kernel: np.ndarray) -> np.ndarray:
    op_map = {
        MORPH_OPEN: cv2.MORPH_OPEN,
        MORPH_CLOSE: cv2.MORPH_CLOSE,
        MORPH_GRADIENT: cv2.MORPH_GRADIENT,
        MORPH_TOPHAT: cv2.MORPH_TOPHAT,
        MORPH_BLACKHAT: cv2.MORPH_BLACKHAT,
    }
    if op not in op_map:
        raise ValueError(f"Unsupported operation: {op}")
    return cv2.morphologyEx(image, op_map[op], kernel.astype(np.uint8))
    

def get_structuring_element(shape: int, ksize: tuple) -> np.ndarray:
    """
    OpenCV-like getStructuringElement.

    Parameters
    ----------
    shape : int
        One of MORPH_RECT, MORPH_CROSS, MORPH_ELLIPSE
    ksize : (h, w) tuple
        Size of the structuring element
    """
    h, w = ksize
    return cv2.getStructuringElement(shape, (w, h))


def close_holes(mask: np.ndarray) -> np.ndarray:
    """Fill holes in a binary mask.
    
    Args:
        mask: Input binary mask
        
    Returns:
        Hole-filled boolean mask
    """
    binary = (mask > 0).astype(np.uint8)
    padded = np.pad(binary, 1, mode="constant", constant_values=0)
    flood_mask = np.zeros((padded.shape[0] + 2, padded.shape[1] + 2), dtype=np.uint8)
    cv2.floodFill(padded, flood_mask, (0, 0), 1)
    holes = padded[1:-1, 1:-1] == 0
    return (binary | holes).astype(bool)
