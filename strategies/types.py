from enum import Enum


class ResultType(Enum):
    url = "url"
    video_url = "video_url"
    items_list = "items_list"
    text = "text"


class Provider(Enum):
    instagram = "instagram"
    tiktok = "tiktok"
    twitter = "twitter"
    youtube = "youtube"
    threads = "threads"


class FilterUrlRegex(Enum):
    instagram = r"https://[w.]*instagram\.com/(reel|share|p)/\S*"
    tiktok = r"https://\S*\.tiktok\.com/\S*"
    twitter = r"https://(?:x|twitter)\.com/\S*"
    youtube = r"https://[w.]*youtube\.com/shorts/\S*"
    threads = r"https://(?:www\.)?threads\.(?:net|com)/(?:t/[\w-]+|@[\w.\-]+/post/[\w-]+)\S*"


class FileType(Enum):
    img = 'img'
    video = 'video'

