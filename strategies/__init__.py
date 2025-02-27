from . import ig, tiktok, x, yt
from .base import Provider, Registry, RegistryItem, get_provider_by_url

__all__ = [
    'registry', 'Provider', 'get_provider_by_url'
]


registry = Registry(
    items={
        Provider.instagram: RegistryItem(
            strategies=[
                ig.InstaloaderStrategy(),
                ig.SnapclipSessionStrategy(),
                ig.SnapclipPlaywrightStrategy(),
                ig.DDInstaStrategy()
            ],
            extract_id=ig.extract_id,
            preprocess_url=ig.preprocess_url,
        ),
        Provider.twitter: RegistryItem(
            strategies=[x.SSSPlaywrightStrategy(), x.TwitterLoadStrategy()],
            extract_id=x.extract_id,
        ),
        Provider.tiktok: RegistryItem(
            strategies=[tiktok.SnaptikSessionStrategy()],
            extract_id=tiktok.extract_id,
            preprocess_url=tiktok.preprocess_url,
        ),
        Provider.youtube: RegistryItem(
            strategies=[yt.PytubeYtStrategy()],
            extract_id=yt.extract_id,
        ),
    }
)
