from enum import Enum


class ResultType(Enum):
    url = "url"
    video_url = "video_url"
    items_list = "items_list"


class Provider(Enum):
    instagram = "instagram"
    tiktok = "tiktok"
    twitter = "twitter"
    youtube = "youtube"
    reddit = "reddit"


class FilterUrlRegex(Enum):
    instagram = r"https://[w.]*instagram\.com/[reel|share|p]*/\S*"
    tiktok = r"https://vm.tiktok.com/\S*|https://[w.]*tiktok.com/"
    twitter = r"https://x.com/\S*"
    youtube = r"https://[w.]*youtube.com/shorts/\S*"
    reddit = r"https://[w.]*reddit\.com/r/\S*/comments/\S*"


class FileType(Enum):
    img = 'img'
    video = 'video'

