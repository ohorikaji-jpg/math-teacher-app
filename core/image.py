import io

from PIL import Image

MAX_API_BYTES = 4_700_000   # 4.7MB（5MB上限に対して余裕を持たせる）
MAX_LONG_SIDE = 1568        # Anthropic推奨の最大長辺px


def compress_for_api(image_bytes: bytes) -> tuple[bytes, str]:
    """
    Anthropic API送信用に画像を圧縮して返す。

    - 長辺が MAX_LONG_SIDE を超える場合は縮小
    - JPEG形式に変換（RGBA/PNG等も含む）
    - 品質を段階的に下げて MAX_API_BYTES 以下に収める
    - 圧縮後も制限を超える場合は ValueError を送出

    Returns:
        (compressed_bytes, "image/jpeg")
    """
    img = Image.open(io.BytesIO(image_bytes))

    # アルファチャンネルや特殊モードはRGBに変換
    if img.mode not in ("RGB",):
        img = img.convert("RGB")

    # 長辺を MAX_LONG_SIDE に縮小
    w, h = img.size
    long_side = max(w, h)
    if long_side > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / long_side
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)

    # JPEG品質を段階的に下げて制限以下に収める
    for quality in [85, 70, 50, 30, 15]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        if len(data) <= MAX_API_BYTES:
            return data, "image/jpeg"

    mb = len(data) / 1024 / 1024
    raise ValueError(
        f"画像を5MB以下に圧縮できませんでした（最低品質でも {mb:.1f}MB）。"
        "より小さな画像を使用してください。"
    )
