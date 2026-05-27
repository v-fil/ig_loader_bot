from . import ig, threads, tiktok, x, yt
from .base import Provider, Registry, RegistryItem, get_provider_by_url

__all__ = [
    'registry', 'Provider', 'get_provider_by_url'
]


registry = Registry(
    items={
        Provider.instagram: RegistryItem(
            strategies=[
                ig.InstaloaderStrategy(),
                ig.FastDLSessionStrategy(),
                ig.FastDLPlaywrightStrategy(),
            ],
            extract_id=ig.extract_id,
            preprocess_url=ig.preprocess_url,
        ),
        Provider.twitter: RegistryItem(
            strategies=[x.FxTwitterStrategy()],
            extract_id=x.extract_id,
        ),
        Provider.tiktok: RegistryItem(
            strategies=[tiktok.SnaptikSessionStrategy()],
            extract_id=tiktok.extract_id,
            preprocess_url=tiktok.preprocess_url,
        ),
        Provider.threads: RegistryItem(
            strategies=[threads.ThreadsStrategy()],
            extract_id=threads.extract_id,
        ),
        Provider.youtube: RegistryItem(
            # disable YouTube for now
            # strategies=[yt.PytubeYtStrategy()],
            strategies=[],
            extract_id=yt.extract_id,
        ),
    }
)
