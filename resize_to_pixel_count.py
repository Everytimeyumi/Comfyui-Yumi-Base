import torch
from PIL import Image
import numpy as np
import math
from nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from comfy.utils import common_reshape

class ResizeImagesToPixelCount:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "pixel_count": ("INT", {"default": 1048576, "min": 64, "max": 10000000}),
                "steps": ("INT", {"default": 64, "min": 1, "max": 1000}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "resize_images"
    CATEGORY = "dataset"

    def resize_images(self, images, pixel_count, steps):
        # Convert tensor to PIL images
        batch_images = []
        for img in images:
            img_np = img.cpu().numpy()
            if img_np.shape[0] == 1:  # Single channel -> grayscale
                img_np = np.tile(img_np, (1, 3, 1, 1))
            img_pil = Image.fromarray((img_np[0].transpose(1, 2, 0) * 255).astype(np.uint8))
            batch_images.append(img_pil)

        resized_images = []

        for img in batch_images:
            w, h = img.size
            current_pixels = w * h
            target_pixels = pixel_count

            # Find best dimensions with ratio preserved
            best_w, best_h = self.find_best_size(w, h, target_pixels, steps)

            # Resize image
            resized_img = img.resize((best_w, best_h), Image.LANCZOS)
            resized_images.append(resized_img)

        # Convert back to tensors
        result = []
        for img in resized_images:
            img_array = np.array(img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_array.transpose(2, 0, 1)).unsqueeze(0)
            result.append(img_tensor)

        return (torch.cat(result, dim=0),)

    def find_best_size(self, w, h, target_pixels, steps):
        """Find best width and height that preserve aspect ratio and match pixel count"""
        ratio = w / h
        best_diff = float('inf')
        best_w, best_h = w, h

        # Generate candidate sizes within a range
        max_dim = int(math.sqrt(target_pixels) * 1.5)
        min_dim = int(math.sqrt(target_pixels) * 0.5)

        for s in range(steps + 1):
            scale = 1.0 + s * 0.01  # Small step increments
            new_w = int(round(math.sqrt(target_pixels * ratio) * scale))
            new_h = int(round(new_w / ratio))

            # Ensure both are reasonable
            if new_w < min_dim or new_h < min_dim or new_w > max_dim or new_h > max_dim:
                continue

            pixels = new_w * new_h
            diff = abs(pixels - target_pixels)
            if diff < best_diff:
                best_diff = diff
                best_w, best_h = new_w, new_h

        return best_w, best_h


# Register the node
NODE_CLASS_MAPPINGS["ResizeImagesToPixelCount"] = ResizeImagesToPixelCount
NODE_DISPLAY_NAME_MAPPINGS["ResizeImagesToPixelCount"] = "Resize Images to Pixel Count"