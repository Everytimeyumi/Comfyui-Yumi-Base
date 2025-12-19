

# 新节点导入
from .script_panel_processor import (
    ScriptPanelProcessor,
    PanelBatchProcessor,
    ImageListCollector,
    SequentialPanelGenerator,
    PanelIteratorForBatch,
    BatchPanelImageGenerator,
    TextDisplayNode,
    PanelImageComposer,
)



# 导入LongCat-Image节点
from .longcat_image_node import LongCatImageLoader, LongCatImageGenerator

# 节点映射
NODE_CLASS_MAPPINGS = {
    # 新节点
    "ScriptPanelProcessor": ScriptPanelProcessor,
    "PanelBatchProcessor": PanelBatchProcessor,
    "ImageListCollector": ImageListCollector,
    "SequentialPanelGenerator": SequentialPanelGenerator,
    "PanelIteratorForBatch": PanelIteratorForBatch,
    "BatchPanelImageGenerator": BatchPanelImageGenerator,
    "TextDisplayNode": TextDisplayNode,
    "PanelImageComposer": PanelImageComposer,
    # ResizeImagesToPixelCount节点

    # LongCat-Image节点
    "LongCatImageLoader": LongCatImageLoader,
    "LongCatImageGenerator": LongCatImageGenerator,
}



# 显示名称映射
NODE_DISPLAY_NAME_MAPPINGS = {
    # 新节点
    "ScriptPanelProcessor": "剧本分镜拆分器",
    "PanelBatchProcessor": "分镜批处理器",
    "ImageListCollector": "图像收集器",
    "SequentialPanelGenerator": "顺序分镜生成器（一键生成）",
    "PanelIteratorForBatch": "批量分镜提取器",
    "BatchPanelImageGenerator": "批量图像生成器",
    "TextDisplayNode": "文本显示器",
    "PanelImageComposer": "分镜图片合成器",
    # ResizeImagesToPixelCount节点显示名称
    "ResizeImagesToPixelCount": "按像素数调整图像大小",
    # LongCat-Image节点显示名称
    "LongCatImageLoader": "加载LongCat-Image模型",
    "LongCatImageGenerator": "LongCat-Image图像生成器",
}



__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']