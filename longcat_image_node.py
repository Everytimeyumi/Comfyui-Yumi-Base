# 文件: d:\xgwork\Comfyui-Yumi-Comics\longcat_image_node.py

import torch
from PIL import Image
from modelscope import AutoProcessor
from longcat_image.models import LongCatImageTransformer2DModel
from longcat_image.pipelines import LongCatImageEditPipeline
import folder_paths

class LongCatImageLoader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model_name": (folder_paths.get_filename_list("models"),),
                "device": (["cuda", "cpu"], {"default": "cuda"}),
                "torch_dtype": (["float32", "float16"], {"default": "float16"}),
            },
            "optional": {
                "use_safetensors": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("MODEL", "CLIP")
    RETURN_NAMES = ("model", "clip")
    FUNCTION = "load_model"
    CATEGORY = "LongCat-Image/Loaders"

    def load_model(self, model_name, device, torch_dtype, use_safetensors=True):
        # 获取模型路径
        checkpoint_dir = folder_paths.get_full_path("models", model_name)
        
        # 设置设备
        device = torch.device(device)
        
        # 加载文本处理器
        text_processor = AutoProcessor.from_pretrained(
            checkpoint_dir, 
            subfolder='tokenizer'
        )
        
        # 加载transformer模型
        transformer = LongCatImageTransformer2DModel.from_pretrained(
            checkpoint_dir,
            subfolder='transformer',
            torch_dtype=torch.float16 if torch_dtype == "float16" else torch.float32,
            use_safetensors=use_safetensors
        ).to(device)
        
        # 创建管道
        pipe = LongCatImageEditPipeline.from_pretrained(
            checkpoint_dir,
            transformer=transformer,
            text_processor=text_processor
        ).to(device)
        
        # 启用CPU卸载以节省VRAM（可选）
        pipe.enable_model_cpu_offload()
        
        # 返回模型和CLIP组件
        return (pipe, text_processor)

class LongCatImageGenerator:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "guidance_scale": ("FLOAT", {"default": 4.5, "min": 0.1, "max": 10.0, "step": 0.1}),
                "num_inference_steps": ("INT", {"default": 50, "min": 1, "max": 1000}),
                "seed": ("INT", {"default": 123456, "min": 0, "max": 999999}),
            },
            "optional": {
                "generator": ("GENERATOR", {"default": None}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"
    CATEGORY = "LongCat-Image/Generators"

    def generate(self, image, prompt, negative_prompt, guidance_scale, num_inference_steps, seed, generator=None):
        # 将PIL图像转换为Tensor
        if isinstance(image, Image.Image):
            img_tensor = torch.from_numpy(np.array(image)).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        else:
            img_tensor = image
        
        # 如果没有提供生成器，创建一个新的
        if generator is None:
            generator = torch.Generator().manual_seed(seed)
        
        # 执行图像生成
        with torch.no_grad():
            output = self.pipe(
                image=img_tensor,
                prompt=prompt,
                negative_prompt=negative_prompt,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                generator=generator
            )
        
        # 返回结果
        return (output.images[0],)

# 注册节点
NODE_CLASS_MAPPINGS.update({
    "LongCatImageLoader": LongCatImageLoader,
    "LongCatImageGenerator": LongCatImageGenerator
})

NODE_DISPLAY_NAME_MAPPINGS.update({
    "LongCatImageLoader": "加载LongCat-Image模型",
    "LongCatImageGenerator": "LongCat-Image图像生成器"
})