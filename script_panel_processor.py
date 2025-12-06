"""
分镜剧本处理节点 - 将剧本拆分为多个分镜提示词
"""
import re
import torch


class ScriptPanelProcessor:
    """剧本转分镜提示词处理器"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "script_text": ("STRING", {
                    "multiline": True,
                    "default": "请输入分镜剧本...\n\n示例格式：\n[分镜1: 全景]\n场景：古老的港口城市\n角色：莉娜\n描述：晨光中，莉娜站在码头边。"
                }),
                "base_prompt": ("STRING", {
                    "multiline": False,
                    "default": "线稿漫画风格，高质量，专业插画"
                }),
            },
        }
    
    RETURN_TYPES = ("PANEL_LIST",)
    RETURN_NAMES = ("panel_list",)
    FUNCTION = "process_script"
    CATEGORY = "漫画工作流/剧本处理"
    
    def process_script(self, script_text, base_prompt):
        """处理剧本文本，拆分成多个分镜提示词"""
        panels = []
        
        # 使用正则表达式匹配分镜块
        panel_pattern = r'\[分镜\s*(\d+).*?\](.*?)(?=\[分镜|\Z)'
        matches = re.findall(panel_pattern, script_text, re.DOTALL)
        
        for panel_num, content in matches:
            # 清理内容
            content = content.strip()
            
            # 提取场景、角色、描述、对话信息
            scene_match = re.search(r'场景[：:]\s*(.+?)(?=\n|$)', content)
            character_match = re.search(r'角色[：:]\s*(.+?)(?=\n|$)', content)
            desc_match = re.search(r'描述[：:]\s*(.+?)(?=\n对话|\n|$)', content, re.DOTALL)
            shot_type_match = re.search(r'分镜\s*\d+\s*[：:]\s*(.+?)(?=\]|$)', content)
            dialogue_match = re.search(r'对话[：:]\s*(.+?)(?=\n|$)', content, re.DOTALL)
            
            scene = scene_match.group(1).strip() if scene_match else ""
            character = character_match.group(1).strip() if character_match else ""
            description = desc_match.group(1).strip() if desc_match else content
            shot_type = shot_type_match.group(1).strip() if shot_type_match else "中景"
            dialogue = dialogue_match.group(1).strip() if dialogue_match else ""
            
            # 组合提示词
            prompt_parts = [base_prompt]
            
            if shot_type:
                prompt_parts.append(shot_type)
            if character:
                prompt_parts.append(f"角色：{character}")
            if scene:
                prompt_parts.append(f"场景：{scene}")
            
            # 如果有对话，添加对话气泡框提示
            if dialogue:
                prompt_parts.append(f"漫画对话气泡框，对话内容：{dialogue}")
            
            if description:
                prompt_parts.append(description)
            
            final_prompt = "，".join(prompt_parts)
            
            panel_data = {
                "index": int(panel_num),
                "prompt": final_prompt,
                "scene": scene,
                "character": character,
                "description": description,
                "shot_type": shot_type,
                "dialogue": dialogue,
                "has_dialogue": bool(dialogue)
            }
            
            panels.append(panel_data)
        
        # 如果没有匹配到分镜格式，尝试按行拆分
        if not panels:
            lines = [line.strip() for line in script_text.split('\n') if line.strip()]
            for idx, line in enumerate(lines, 1):
                if line:
                    panel_data = {
                        "index": idx,
                        "prompt": f"{base_prompt}，{line}",
                        "scene": "",
                        "character": "",
                        "description": line,
                        "shot_type": "中景",
                        "dialogue": "",
                        "has_dialogue": False
                    }
                    panels.append(panel_data)
        
        return (panels,)


class PanelBatchProcessor:
    """分镜批处理器 - 逐个输出分镜提示词用于图像生成"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "panel_list": ("PANEL_LIST",),
                "current_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 9999,
                    "step": 1
                }),
            },
        }
    
    RETURN_TYPES = ("STRING", "INT", "INT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("prompt", "current_index", "total_panels", "has_next", "panel_info")
    FUNCTION = "get_panel"
    CATEGORY = "漫画工作流/剧本处理"
    
    def get_panel(self, panel_list, current_index):
        """获取当前索引的分镜提示词"""
        total = len(panel_list)
        
        if current_index >= total:
            # 超出范围，返回最后一个
            current_index = total - 1 if total > 0 else 0
        
        if total == 0:
            return ("", 0, 0, False, "没有分镜数据")
        
        panel = panel_list[current_index]
        prompt = panel.get("prompt", "")
        has_next = current_index < total - 1
        
        # 创建面板信息字符串
        panel_info = f"分镜 {current_index + 1}/{total}\n"
        panel_info += f"镜头类型: {panel.get('shot_type', '')}\n"
        panel_info += f"场景: {panel.get('scene', '')}\n"
        panel_info += f"角色: {panel.get('character', '')}\n"
        panel_info += f"描述: {panel.get('description', '')}\n"
        if panel.get('has_dialogue'):
            panel_info += f"对话: {panel.get('dialogue', '')}"
        
        return (prompt, current_index, total, has_next, panel_info)


class ImageListCollector:
    """图像列表收集器 - 收集所有生成的图像"""
    
    def __init__(self):
        self.images = []
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "reset": ("BOOLEAN", {
                    "default": False
                }),
            },
            "optional": {
                "image_list": ("IMAGE",),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image_list",)
    FUNCTION = "collect_image"
    CATEGORY = "漫画工作流/图像处理"
    
    def collect_image(self, image, reset, image_list=None):
        """收集图像到列表"""
        import torch
        
        if reset or image_list is None:
            # 重置或首次收集
            return (image,)
        else:
            # 追加图像
            combined = torch.cat([image_list, image], dim=0)
            return (combined,)


class SequentialPanelGenerator:
    """顺序分镜生成器 - 自动遍历所有分镜并生成图像"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "panel_list": ("PANEL_LIST",),
                "clip": ("CLIP",),
                "model": ("MODEL",),
                "vae": ("VAE",),
                "width": ("INT", {
                    "default": 1280,
                    "min": 256,
                    "max": 4096,
                    "step": 64
                }),
                "height": ("INT", {
                    "default": 720,
                    "min": 256,
                    "max": 4096,
                    "step": 64
                }),
                "steps": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 100
                }),
                "cfg": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 20.0,
                    "step": 0.1
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff
                }),
                "sampler_name": (["euler", "euler_a", "dpmpp_2m", "dpmpp_sde"],{"default": "euler"}),
                "scheduler": (["simple", "normal", "karras", "exponential", "sgm_uniform"],{"default": "simple"}),
            },
        }
    
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "info")
    FUNCTION = "generate_all_panels"
    CATEGORY = "漫画工作流/自动生成"
    
    def generate_all_panels(self, panel_list, clip, model, vae, width, height, 
                          steps, cfg, seed, sampler_name, scheduler):
        """遍历所有分镜并生成图像"""
        import torch
        import comfy.sample
        import comfy.samplers
        import comfy.utils
        import nodes
        
        if not panel_list:
            # 返回空图像
            empty_image = torch.zeros((1, height, width, 3))
            return (empty_image, "错误：没有分镜数据")
        
        all_images = []
        total = len(panel_list)
        
        # 遍历每个分镜
        for idx, panel in enumerate(panel_list):
            prompt_text = panel.get("prompt", "")
            
            # 文本编码
            tokens = clip.tokenize(prompt_text)
            cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
            positive = [[cond, {"pooled_output": pooled}]]
            
            # 负面提示词（空）
            tokens_neg = clip.tokenize("")
            cond_neg, pooled_neg = clip.encode_from_tokens(tokens_neg, return_pooled=True)
            negative = [[cond_neg, {"pooled_output": pooled_neg}]]
            
            # 使用标准方式创建空latent
            latent_image = torch.zeros([1, 4, height // 8, width // 8], device=comfy.model_management.intermediate_device())
            
            # 采样
            samples = comfy.sample.sample(
                model,
                torch.randn_like(latent_image, device=comfy.model_management.intermediate_device()),
                steps,
                cfg,
                sampler_name,
                scheduler,
                positive,
                negative,
                latent_image,
                denoise=1.0,
                seed=seed + idx,  # 每个分镜使用不同的种子
            )
            
            # 解码
            image = vae.decode(samples["samples"])
            all_images.append(image)
        
        # 合并所有图像
        final_images = torch.cat(all_images, dim=0)
        info = f"成功生成 {total} 个分镜图像"
        
        return (final_images, info)


class PanelIteratorForBatch:
    """批量分镜迭代器 - 提取所有分镜提示词列表"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "panel_list": ("PANEL_LIST",),
            },
        }
    
    RETURN_TYPES = ("STRING", "INT", "STRING")
    RETURN_NAMES = ("prompts", "total_count", "info")
    OUTPUT_IS_LIST = (True, False, False)
    FUNCTION = "extract_all_prompts"
    CATEGORY = "漫画工作流/剧本处理"
    
    def extract_all_prompts(self, panel_list):
        """提取所有分镜的提示词"""
        if not panel_list:
            return ([""], 0, "没有分镜数据")
        
        prompts = [panel.get("prompt", "") for panel in panel_list]
        total = len(prompts)
        
        # 创建信息字符串
        info = f"共 {total} 个分镜\n"
        for idx, panel in enumerate(panel_list, 1):
            info += f"\n分镜{idx}:"
            if panel.get('has_dialogue'):
                info += f" [有对话: {panel.get('dialogue', '')}]"
            else:
                info += " [无对话]"
        
        return (prompts, total, info)


class BatchPanelImageGenerator:
    """批量分镜图像生成器 - 根据提示词列表批量生成"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompts": ("STRING", {"forceInput": True}),
                "clip": ("CLIP",),
                "model": ("MODEL",),
                "vae": ("VAE",),
                "width": ("INT", {
                    "default": 1280,
                    "min": 256,
                    "max": 4096,
                    "step": 64
                }),
                "height": ("INT", {
                    "default": 720,
                    "min": 256,
                    "max": 4096,
                    "step": 64
                }),
                "steps": ("INT", {
                    "default": 10,
                    "min": 1,
                    "max": 100
                }),
                "cfg": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 20.0,
                    "step": 0.1
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff
                }),
                "sampler_name": (["euler", "euler_a", "dpmpp_2m", "dpmpp_sde"],{"default": "euler"}),
                "scheduler": (["simple", "normal", "karras", "exponential", "sgm_uniform"],{"default": "simple"}),
            },
        }
    
    INPUT_IS_LIST = True
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "result_info")
    FUNCTION = "generate_batch_images"
    CATEGORY = "漫画工作流/自动生成"
    
    def generate_batch_images(self, prompts, clip, model, vae, width, height, 
                            steps, cfg, seed, sampler_name, scheduler):
        """批量生成图像"""
        import torch
        import nodes
        
        # 提取单个值
        clip = clip[0]
        model = model[0]
        vae = vae[0]
        width = width[0]
        height = height[0]
        steps = steps[0]
        cfg = cfg[0]
        seed = seed[0]
        sampler_name = sampler_name[0]
        scheduler = scheduler[0]
        
        if not prompts:
            empty_image = torch.zeros((1, height, width, 3))
            return (empty_image, "错误：没有提示词")
        
        all_images = []
        total = len(prompts)
        
        # 使用ComfyUI标准节点
        clip_encoder = nodes.CLIPTextEncode()
        empty_latent = nodes.EmptyLatentImage()
        sampler = nodes.KSampler()
        vae_decoder = nodes.VAEDecode()
        
        # 遍历每个提示词生成图像
        for idx, prompt_text in enumerate(prompts):
            # 正面提示词编码
            positive_cond = clip_encoder.encode(clip=clip, text=prompt_text)
            
            # 负面提示词编码
            negative_cond = clip_encoder.encode(clip=clip, text="")
            
            # 创建空latent
            latent = empty_latent.generate(width=width, height=height, batch_size=1)
            
            # 采样
            samples = sampler.sample(
                model=model,
                seed=seed + idx,
                steps=steps,
                cfg=cfg,
                sampler_name=sampler_name,
                scheduler=scheduler,
                positive=positive_cond[0],
                negative=negative_cond[0],
                latent_image=latent[0],
                denoise=1.0
            )
            
            # 解码
            image = vae_decoder.decode(samples=samples[0], vae=vae)
            all_images.append(image[0])
        
        # 合并所有图像
        final_images = torch.cat(all_images, dim=0)
        result_info = f"成功生成 {total} 个分镜图像，每个分镜已独立保存"
        
        return (final_images, result_info)


class TextDisplayNode:
    """文本显示节点"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True}),
            },
        }
    
    INPUT_IS_LIST = False
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_NODE = True
    FUNCTION = "display_text"
    CATEGORY = "漫画工作流/工具"
    
    def display_text(self, text):
        """显示文本内容"""
        print(f"\n[TextDisplayNode] {text}")
        return {"ui": {"text": (text,)}, "result": (text,)}


class PanelImageComposer:
    """分镜图片合成器 - 根据内容复杂度将多张图片合成一张"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "panel_list": ("PANEL_LIST",),
                "target_width": ("INT", {"default": 1280, "min": 256, "max": 4096, "step": 64}),
                "min_dialogue_length": ("INT", {"default": 10, "min": 1, "max": 100}),
                "min_description_length": ("INT", {"default": 20, "min": 1, "max": 200}),
            }
        }
    
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("composed_images", "info")
    FUNCTION = "compose_images"
    CATEGORY = "漫画工作流/图像处理"
    
    def compose_images(self, images, panel_list, target_width, min_dialogue_length, min_description_length):
        """根据内容复杂度合成图片，保持宽度为1280"""
        import torch.nn.functional as F
        
        if images is None or len(images) == 0:
            return (images, "错误：没有输入图像")
        
        if len(images) != len(panel_list):
            return (images, f"错误：图像数量({len(images)})与分镜数量({len(panel_list)})不匹配")
        
        print(f"\n[PanelImageComposer] 输入图像形状: {images.shape}")
        print(f"[PanelImageComposer] 分镜数量: {len(panel_list)}")
        
        # 缩放所有图片使宽度为target_width
        scaled_images = []
        for i, img in enumerate(images):
            # img 从批次中提取: [H, W, C]
            if img.dim() == 4:
                img = img[0]  # [H, W, C]
            
            h, w = img.shape[0], img.shape[1]
            new_h = int(h * target_width / w)
            
            # 转换为 [C, H, W] 格式用于缩放
            img_chw = img.permute(2, 0, 1).unsqueeze(0)  # [1, C, H, W]
            scaled = F.interpolate(img_chw, size=(new_h, target_width), mode='bilinear', align_corners=False)
            # 转回 [H, W, C]
            scaled_img = scaled[0].permute(1, 2, 0)  # [H, W, C]
            scaled_images.append(scaled_img)
            print(f"[缩放] 分镜{i+1}: [{h}, {w}, 3] -> [{new_h}, {target_width}, 3]")
        
        # 合成逻辑
        result_images = []
        info_lines = [f"原始图像数量: {len(images)}"]
        
        i = 0
        while i < len(scaled_images):
            current_panel = panel_list[i]
            is_current_simple = self._is_panel_simple(current_panel, min_dialogue_length, min_description_length)
            
            # 判断是否能横向合并
            can_merge_horizontally = False
            if i < len(scaled_images) - 1:
                next_panel = panel_list[i + 1]
                is_next_simple = self._is_panel_simple(next_panel, min_dialogue_length, min_description_length)
                can_merge_horizontally = is_current_simple and is_next_simple
            
            if can_merge_horizontally:
                # 横向合并两个简单分镜
                img1 = scaled_images[i]  # [H, W, C]
                img2 = scaled_images[i + 1]  # [H, W, C]
                
                # 每张图宽度变为target_width/2
                h1, h2 = img1.shape[0], img2.shape[0]
                half_width = target_width // 2
                
                # 缩放到半宽
                new_h1 = int(h1 * half_width / target_width)
                new_h2 = int(h2 * half_width / target_width)
                
                img1_chw = img1.permute(2, 0, 1).unsqueeze(0)  # [1, C, H, W]
                img2_chw = img2.permute(2, 0, 1).unsqueeze(0)
                
                scaled1 = F.interpolate(img1_chw, size=(new_h1, half_width), mode='bilinear', align_corners=False)
                scaled2 = F.interpolate(img2_chw, size=(new_h2, half_width), mode='bilinear', align_corners=False)
                
                scaled1 = scaled1[0].permute(1, 2, 0)  # [H, W, C]
                scaled2 = scaled2[0].permute(1, 2, 0)
                
                # 合并：高度取最大值，宽度为target_width
                target_h = max(new_h1, new_h2)
                merged = torch.zeros((target_h, target_width, 3), dtype=img1.dtype, device=img1.device)
                
                # 左侧图片（居中）
                start_y1 = (target_h - new_h1) // 2
                merged[start_y1:start_y1+new_h1, :half_width, :] = scaled1
                
                # 右侧图片（居中）
                start_y2 = (target_h - new_h2) // 2
                merged[start_y2:start_y2+new_h2, half_width:, :] = scaled2
                
                result_images.append(merged)
                info_lines.append(f"横向合并分镜 {i+1} 和 {i+2}")
                print(f"[横向合并] 分镜{i+1}+{i+2} -> [{target_h}, {target_width}, 3]")
                i += 2
            else:
                # 内容复杂，直接添加（已缩放到target_width）
                result_images.append(scaled_images[i])
                info_lines.append(f"单独分镜 {i+1}")
                i += 1
        
        # 垂直拼接所有结果图片
        if result_images:
            # 计算总高度
            total_height = sum(img.shape[1] for img in result_images)
            final_image = torch.zeros((1, total_height, target_width, 3), dtype=images.dtype, device=images.device)
            
            current_y = 0
            for img in result_images:
                h = img.shape[0]
                final_image[0, current_y:current_y+h, :, :] = img
                current_y += h
            
            info = "\n".join(info_lines)
            info += f"\n\n最终输出: 1张图 ({target_width}x{total_height})"
            print(f"[PanelImageComposer] 最终输出: {final_image.shape}")
            print(f"[PanelImageComposer] {info}")
            
            return (final_image, info)
        else:
            return (images, "错误：处理失败")
    
    def _is_panel_simple(self, panel, min_dialogue_length, min_description_length):
        """判断分镜是否简单（没有对话）"""
        dialogue = panel.get("dialogue", "")
        # 没有对话即为简单分镜
        return len(dialogue.strip()) == 0
    
    def _merge_two_images_horizontally(self, img1, img2):
        """水平合并两张图片"""
        # img1, img2 格式: [1, H, W, C]
        h1, w1 = img1.shape[1], img1.shape[2]
        h2, w2 = img2.shape[1], img2.shape[2]
        
        print(f"[合并] img1形状: {img1.shape}, img2形状: {img2.shape}")
        
        # 计算目标尺寸（高度取较大值，宽度相加）
        target_h = max(h1, h2)
        target_w = w1 + w2
        
        # 创建新图像（使用输入图像的数据类型和设备）
        merged = torch.zeros((1, target_h, target_w, 3), dtype=img1.dtype, device=img1.device)
        
        # 左侧图片（居中放置）
        start_y1 = (target_h - h1) // 2
        merged[0, start_y1:start_y1+h1, :w1, :] = img1[0]
        
        # 右侧图片（居中放置）
        start_y2 = (target_h - h2) // 2
        merged[0, start_y2:start_y2+h2, w1:w1+w2, :] = img2[0]
        
        print(f"[合并] 输出形状: {merged.shape}")
        return merged
    
    def _merge_two_images_vertically(self, img1, img2):
        """垂直合并两张图片"""
        # img1, img2 格式: [1, H, W, C]
        h1, w1 = img1.shape[1], img1.shape[2]
        h2, w2 = img2.shape[1], img2.shape[2]
        
        # 计算目标尺寸（宽度取较大值，高度相加）
        target_h = h1 + h2
        target_w = max(w1, w2)
        
        # 创建新图像
        merged = torch.zeros((1, target_h, target_w, 3), dtype=img1.dtype, device=img1.device)
        
        # 上方图片（居中放置）
        start_x1 = (target_w - w1) // 2
        merged[0, :h1, start_x1:start_x1+w1, :] = img1[0]
        
        # 下方图片（居中放置）
        start_x2 = (target_w - w2) // 2
        merged[0, h1:h1+h2, start_x2:start_x2+w2, :] = img2[0]
        
        return merged
    
    def _merge_three_images_grid(self, img1, img2, img3):
        """网格合并三张图片（前两张水平排列，第三张在下方）"""
        # 先水平合并前两张图片
        top_merged = self._merge_two_images_horizontally(img1, img2)
        
        # 再垂直合并结果与第三张图片
        final_merged = self._merge_two_images_vertically(top_merged, img3)
        
        return final_merged


NODE_CLASS_MAPPINGS = {
    "ScriptPanelProcessor": ScriptPanelProcessor,
    "PanelBatchProcessor": PanelBatchProcessor,
    "ImageListCollector": ImageListCollector,
    "SequentialPanelGenerator": SequentialPanelGenerator,
    "PanelIteratorForBatch": PanelIteratorForBatch,
    "BatchPanelImageGenerator": BatchPanelImageGenerator,
    "TextDisplayNode": TextDisplayNode,
    "PanelImageComposer": PanelImageComposer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ScriptPanelProcessor": "剧本分镜拆分器",
    "PanelBatchProcessor": "分镜批处理器",
    "ImageListCollector": "图像收集器",
    "SequentialPanelGenerator": "顺序分镜生成器",
    "PanelIteratorForBatch": "批量分镜提取器",
    "BatchPanelImageGenerator": "批量图像生成器",
    "TextDisplayNode": "文本显示器",
    "PanelImageComposer": "分镜图片合成器",
}
