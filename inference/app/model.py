import os
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn.functional as F
from torch import nn


def _pair(value):
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value, value)


def _build_act(name: Optional[str]) -> Optional[nn.Module]:
    if name is None:
        return None
    acts = {
        "relu": nn.ReLU,
        "relu6": nn.ReLU6,
        "hswish": nn.Hardswish,
        "silu": nn.SiLU,
        "gelu": lambda: nn.GELU(approximate="tanh"),
    }
    if name not in acts:
        raise ValueError(f"Unsupported activation: {name}")
    return acts[name]()


def _build_norm(name: Optional[str], num_features: int) -> Optional[nn.Module]:
    if name is None:
        return None
    if name == "bn2d":
        return nn.BatchNorm2d(num_features)
    if name == "ln":
        return nn.LayerNorm(num_features)
    raise ValueError(f"Unsupported normalization: {name}")


class OpSequential(nn.Module):
    """Official EfficientViT-style sequential wrapper that skips None ops."""

    def __init__(self, ops):
        super().__init__()
        self.op_list = nn.ModuleList([op for op in ops if op is not None])

    def forward(self, x):
        for op in self.op_list:
            x = op(x)
        return x


class ConvLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size=3,
        stride=1,
        padding: Optional[int] = None,
        groups=1,
        use_bias=False,
        dropout=0.0,
        norm="bn2d",
        act_func="hswish",
    ):
        super().__init__()
        if padding is None:
            padding = kernel_size // 2
        self.dropout = nn.Dropout2d(dropout) if dropout > 0 else None
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size,
            stride,
            padding,
            groups=groups,
            bias=use_bias,
        )
        self.norm = _build_norm(norm, out_channels)
        self.act = _build_act(act_func)

    def forward(self, x):
        if self.dropout is not None:
            x = self.dropout(x)
        x = self.conv(x)
        if self.norm is not None:
            x = self.norm(x)
        if self.act is not None:
            x = self.act(x)
        return x


class LinearLayer(nn.Module):
    def __init__(self, in_features, out_features, use_bias=True, dropout=0.0, norm=None, act_func=None):
        super().__init__()
        self.dropout = nn.Dropout(dropout) if dropout > 0 else None
        self.linear = nn.Linear(in_features, out_features, bias=use_bias)
        self.norm = _build_norm(norm, out_features)
        self.act = _build_act(act_func)

    def forward(self, x):
        if self.dropout is not None:
            x = self.dropout(x)
        x = self.linear(x)
        if self.norm is not None:
            x = self.norm(x)
        if self.act is not None:
            x = self.act(x)
        return x


class IdentityLayer(nn.Module):
    def forward(self, x):
        return x


class ResidualBlock(nn.Module):
    def __init__(self, main: nn.Module, shortcut: Optional[nn.Module]):
        super().__init__()
        self.main = main
        self.shortcut = shortcut

    def forward(self, x):
        out = self.main(x)
        if self.shortcut is None:
            return out
        return out + self.shortcut(x)


class DSConv(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        stride=1,
        use_bias=False,
        norm="bn2d",
        act_func=("hswish", None),
    ):
        super().__init__()
        use_bias = _triple_from_pair(use_bias)
        norm = _triple_from_pair(norm)
        act_func = _triple_from_pair(act_func)
        self.depth_conv = ConvLayer(
            in_channels,
            in_channels,
            3,
            stride,
            groups=in_channels,
            use_bias=use_bias[0],
            norm=norm[0],
            act_func=act_func[0],
        )
        self.point_conv = ConvLayer(
            in_channels,
            out_channels,
            1,
            use_bias=use_bias[-1],
            norm=norm[-1],
            act_func=act_func[-1],
        )

    def forward(self, x):
        return self.point_conv(self.depth_conv(x))


class MBConv(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        stride=1,
        expand_ratio=4,
        use_bias=False,
        norm="bn2d",
        act_func=("hswish", "hswish", None),
    ):
        super().__init__()
        mid_channels = round(in_channels * expand_ratio)
        use_bias = _triple_from_pair(use_bias)
        norm = _triple_from_pair(norm)
        act_func = _triple_from_pair(act_func)
        self.inverted_conv = ConvLayer(
            in_channels,
            mid_channels,
            1,
            use_bias=use_bias[0],
            norm=norm[0],
            act_func=act_func[0],
        )
        self.depth_conv = ConvLayer(
            mid_channels,
            mid_channels,
            3,
            stride,
            groups=mid_channels,
            use_bias=use_bias[1],
            norm=norm[1],
            act_func=act_func[1],
        )
        self.point_conv = ConvLayer(
            mid_channels,
            out_channels,
            1,
            use_bias=use_bias[2],
            norm=norm[2],
            act_func=act_func[2],
        )

    def forward(self, x):
        x = self.inverted_conv(x)
        x = self.depth_conv(x)
        return self.point_conv(x)


def _triple_from_pair(value):
    values = _pair(value)
    if len(values) == 1:
        return values * 3
    if len(values) == 2:
        return (values[0], values[0], values[1])
    return values


class LiteMLA(nn.Module):
    """EfficientViT lightweight multi-scale linear attention."""

    def __init__(self, in_channels: int, dim=16, scales=(5,), eps=1.0e-6, norm="bn2d", act_func=None):
        super().__init__()
        heads = max(1, in_channels // dim)
        self.dim = dim
        self.heads = heads
        self.total_dim = heads * dim
        self.eps = eps

        self.qkv = ConvLayer(in_channels, 3 * self.total_dim, 1, use_bias=True, norm=None, act_func=None)
        self.aggreg = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Conv2d(
                        3 * self.total_dim,
                        3 * self.total_dim,
                        kernel_size=scale,
                        padding=scale // 2,
                        groups=3 * self.total_dim,
                        bias=True,
                    ),
                    nn.Conv2d(3 * self.total_dim, 3 * self.total_dim, kernel_size=1, groups=3 * heads, bias=True),
                )
                for scale in scales
            ]
        )
        multi_scale_dim = self.total_dim * (1 + len(scales))
        self.proj = ConvLayer(multi_scale_dim, in_channels, 1, use_bias=False, norm=norm, act_func=act_func)

    def _linear_attention(self, qkv):
        b, _, h, w = qkv.shape
        qkv = qkv.reshape(b, 3, -1, self.dim, h * w)
        q, k, v = qkv[:, 0], qkv[:, 1], qkv[:, 2]
        q = F.relu(q)
        k = F.relu(k)
        context = torch.matmul(v, k.transpose(-1, -2))
        out = torch.matmul(context, q)
        normalizer = (q * k.sum(dim=-1, keepdim=True)).sum(dim=-2, keepdim=True).clamp_min(self.eps)
        out = out / normalizer
        return out.reshape(b, -1, h, w)

    def forward(self, x):
        qkv = self.qkv(x)
        multi_scale_qkv = [qkv]
        multi_scale_qkv.extend(op(qkv) for op in self.aggreg)
        qkv = torch.cat(multi_scale_qkv, dim=1)
        return self.proj(self._linear_attention(qkv))


class EfficientViTBlock(nn.Module):
    def __init__(self, in_channels: int, dim=16, expand_ratio=4, norm="bn2d", act_func="hswish"):
        super().__init__()
        self.context_module = ResidualBlock(
            LiteMLA(in_channels, dim=dim, norm=norm),
            IdentityLayer(),
        )
        self.local_module = ResidualBlock(
            MBConv(in_channels, in_channels, expand_ratio=expand_ratio, norm=norm, act_func=(act_func, act_func, None)),
            IdentityLayer(),
        )

    def forward(self, x):
        x = self.context_module(x)
        return self.local_module(x)


class EfficientViTBackbone(nn.Module):
    """B-family EfficientViT backbone following mit-han-lab/efficientvit."""

    def __init__(
        self,
        width_list: list[int],
        depth_list: list[int],
        in_channels=3,
        dim=16,
        expand_ratio=4,
        norm="bn2d",
        act_func="hswish",
    ):
        super().__init__()
        self.width_list = []
        input_stem = [ConvLayer(in_channels, width_list[0], stride=2, norm=norm, act_func=act_func)]
        for _ in range(depth_list[0]):
            block = self.build_local_block(width_list[0], width_list[0], 1, 1, norm, act_func)
            input_stem.append(ResidualBlock(block, IdentityLayer()))
        in_channels = width_list[0]
        self.input_stem = OpSequential(input_stem)
        self.width_list.append(in_channels)

        stages = []
        for w, d in zip(width_list[1:3], depth_list[1:3]):
            stage = []
            for i in range(d):
                stride = 2 if i == 0 else 1
                block = self.build_local_block(in_channels, w, stride, expand_ratio, norm, act_func)
                stage.append(ResidualBlock(block, IdentityLayer() if stride == 1 and in_channels == w else None))
                in_channels = w
            stages.append(OpSequential(stage))
            self.width_list.append(in_channels)

        for w, d in zip(width_list[3:], depth_list[3:]):
            stage = []
            block = self.build_local_block(in_channels, w, 2, expand_ratio, norm, act_func, fewer_norm=True)
            stage.append(ResidualBlock(block, None))
            in_channels = w
            for _ in range(d):
                stage.append(EfficientViTBlock(in_channels, dim=dim, expand_ratio=expand_ratio, norm=norm, act_func=act_func))
            stages.append(OpSequential(stage))
            self.width_list.append(in_channels)
        self.stages = nn.ModuleList(stages)

    @staticmethod
    def build_local_block(
        in_channels: int,
        out_channels: int,
        stride: int,
        expand_ratio: float,
        norm: str,
        act_func: str,
        fewer_norm: bool = False,
    ) -> nn.Module:
        if expand_ratio == 1:
            return DSConv(
                in_channels,
                out_channels,
                stride=stride,
                use_bias=(True, False) if fewer_norm else False,
                norm=(None, norm) if fewer_norm else norm,
                act_func=(act_func, None),
            )
        return MBConv(
            in_channels,
            out_channels,
            stride=stride,
            expand_ratio=expand_ratio,
            use_bias=(True, True, False) if fewer_norm else False,
            norm=(None, None, norm) if fewer_norm else norm,
            act_func=(act_func, act_func, None),
        )

    def forward(self, x):
        output_dict = {"input": x}
        output_dict["stage0"] = x = self.input_stem(x)
        for stage_id, stage in enumerate(self.stages, 1):
            output_dict[f"stage{stage_id}"] = x = stage(x)
        output_dict["stage_final"] = x
        return output_dict


@dataclass(frozen=True)
class EfficientViTVariant:
    width_list: list[int]
    depth_list: list[int]
    dim: int
    cls_width_list: list[int]
    seg_head_width: int
    seg_head_depth: int


EFFICIENTVIT_B_VARIANTS = {
    "b0": EfficientViTVariant([8, 16, 32, 64, 128], [1, 2, 2, 2, 2], 16, [1024, 1280], 32, 1),
    "b1": EfficientViTVariant([16, 32, 64, 128, 256], [1, 2, 3, 3, 4], 16, [1536, 1600], 64, 3),
    "b2": EfficientViTVariant([24, 48, 96, 192, 384], [1, 3, 4, 4, 6], 32, [2304, 2560], 96, 3),
    "b3": EfficientViTVariant([32, 64, 128, 256, 512], [1, 4, 6, 6, 9], 32, [2304, 2560], 128, 3),
}


def _normalize_variant_name(variant: str) -> str:
    variant = variant.lower().replace("efficientvit_cls_", "").replace("efficientvit_", "")
    if variant not in EFFICIENTVIT_B_VARIANTS:
        raise ValueError(f"Unsupported EfficientViT variant: {variant}")
    return variant


class ClsHead(nn.Module):
    def __init__(self, in_channels: int, width_list: list[int], n_classes: int, dropout=0.0, act_func="hswish"):
        super().__init__()
        self.ops = OpSequential(
            [
                ConvLayer(in_channels, width_list[0], 1, norm="bn2d", act_func=act_func),
                nn.AdaptiveAvgPool2d(1),
            ]
        )
        self.classifier = OpSequential(
            [
                LinearLayer(width_list[0], width_list[1], use_bias=False, norm="ln", act_func=act_func),
                LinearLayer(width_list[1], n_classes, use_bias=True, dropout=dropout),
            ]
        )

    def forward(self, feed_dict):
        x = self.ops(feed_dict["stage_final"]).flatten(1)
        return self.classifier(x)


class SegHead(nn.Module):
    def __init__(
        self,
        fid_list: list[str],
        in_channel_list: list[int],
        stride_list: list[int],
        head_stride: int,
        head_width: int,
        head_depth: int,
        n_classes: int,
        expand_ratio=4,
        final_expand=4,
        act_func="hswish",
    ):
        super().__init__()
        self.fid_list = fid_list
        self.input_ops = nn.ModuleDict()
        for fid, in_channels, stride in zip(fid_list, in_channel_list, stride_list):
            factor = stride // head_stride
            ops = [ConvLayer(in_channels, head_width, 1, norm="bn2d", act_func=None)]
            if factor != 1:
                ops.append(nn.Upsample(scale_factor=factor, mode="bilinear", align_corners=False))
            self.input_ops[fid] = OpSequential(ops)

        self.middle = OpSequential(
            [
                ResidualBlock(
                    MBConv(head_width, head_width, expand_ratio=expand_ratio, act_func=(act_func, act_func, None)),
                    IdentityLayer(),
                )
                for _ in range(head_depth)
            ]
        )
        output_width = head_width if final_expand is None else head_width * final_expand
        self.output = OpSequential(
            [
                None if final_expand is None else ConvLayer(head_width, output_width, 1, norm="bn2d", act_func=act_func),
                ConvLayer(output_width, n_classes, 1, use_bias=True, norm=None, act_func=None),
            ]
        )

    def forward(self, feed_dict):
        features = [self.input_ops[fid](feed_dict[fid]) for fid in self.fid_list]
        x = torch.stack(features, dim=0).sum(dim=0)
        return self.output(self.middle(x))


class EfficientViTMultiTask(nn.Module):
    """EfficientViT backbone with bronchoscopy location, segmentation and abnormality heads."""

    def __init__(
        self,
        variant="efficientvit_b1",
        location_classes=31,
        abnormality_classes=6,
        segmentation_classes=1,
    ):
        super().__init__()
        variant_name = _normalize_variant_name(variant)
        cfg = EFFICIENTVIT_B_VARIANTS[variant_name]
        self.variant = variant_name
        self.backbone = EfficientViTBackbone(cfg.width_list, cfg.depth_list, dim=cfg.dim)
        self.location_head = ClsHead(cfg.width_list[-1], cfg.cls_width_list, location_classes)
        self.abnormality_head = ClsHead(cfg.width_list[-1], cfg.cls_width_list, abnormality_classes)
        self.segmentation_head = SegHead(
            fid_list=["stage4", "stage3", "stage2"],
            in_channel_list=[cfg.width_list[4], cfg.width_list[3], cfg.width_list[2]],
            stride_list=[32, 16, 8],
            head_stride=8,
            head_width=cfg.seg_head_width,
            head_depth=cfg.seg_head_depth,
            n_classes=segmentation_classes,
        )

    def forward(self, x):
        input_size = x.shape[-2:]
        feed_dict = self.backbone(x)
        segmentation = self.segmentation_head(feed_dict)
        segmentation = F.interpolate(segmentation, size=input_size, mode="bilinear", align_corners=False)
        return {
            "location": self.location_head(feed_dict),
            "segmentation": segmentation,
            "abnormality": self.abnormality_head(feed_dict),
        }


def _extract_state_dict(checkpoint):
    if not isinstance(checkpoint, dict):
        return checkpoint
    for key in ("state_dict", "model_state_dict", "model"):
        value = checkpoint.get(key)
        if isinstance(value, dict):
            return value
    return checkpoint


def _strip_prefixes(state_dict):
    prefixes = ("module.", "model.")
    cleaned = {}
    for key, value in state_dict.items():
        for prefix in prefixes:
            if key.startswith(prefix):
                key = key[len(prefix) :]
        cleaned[key] = value
    return cleaned


def _load_compatible_weights(model: nn.Module, state_dict) -> None:
    state_dict = _strip_prefixes(_extract_state_dict(state_dict))
    model_state = model.state_dict()
    compatible = {
        key: value
        for key, value in state_dict.items()
        if key in model_state and hasattr(value, "shape") and value.shape == model_state[key].shape
    }
    model.load_state_dict(compatible, strict=False)


def load_model(model_path, device):
    variant = os.getenv("MODEL_VARIANT", "efficientvit_b1")
    location_classes = int(os.getenv("NUM_LOCATION_CLASSES", "31"))
    abnormality_classes = int(os.getenv("NUM_ABNORMALITY_CLASSES", "6"))
    model = EfficientViTMultiTask(
        variant=variant,
        location_classes=location_classes,
        abnormality_classes=abnormality_classes,
    ).to(device)
    if model_path and os.path.exists(model_path):
        state = torch.load(model_path, map_location=device)
        _load_compatible_weights(model, state)
    model.eval()
    return model
