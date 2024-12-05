from .base import Registry, RegistryItem, Provider
from . import tiktok, ig, x, yt

__all__ = [
    'registry', 'Provider'
]


registry = Registry(
    items={
        Provider.instagram: RegistryItem(
            strategies=[ig.SnapclipPlaywrightStrategy(), ig.DDInstaStrategy()],
            extract_id=ig.extract_id,
        ),
        Provider.twitter: RegistryItem(
            strategies=[x.SSSPlaywrightStrategy(), x.TwitterLoadStrategy()],
            extract_id=x.extract_id,
        ),
        Provider.tiktok: RegistryItem(
            strategies=[tiktok.SnaptikSessionStrategy()],
            extract_id=tiktok.extract_id
        ),
        Provider.youtube: RegistryItem(
            strategies=[yt.PytubeYtStrategy()],
            extract_id=yt.extract_id,
        )
    }
)
