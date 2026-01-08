from typing import List

import utils
from .config_entry import ConfigEntry
from .model import Model

class FetchTask(Model):
    """
    A list fetch task is sent to the fetching-plugin so it knows what
    to fetch from Skool. The Fetch tasks are generated on the fly.
    """
    type: str = "posts" # members, one_community, one_profile, posts, likes
    communitySlug: str = "" # always needed
    pageParam: int = 1 # might be ignored
    userSkoolHexId: str = "" # might be ignored
    postSkoolHexId: str = "" # might be ignored
    communitySkoolHexId: str = "" # might be ignored

    @classmethod
    def generateFetchTasks(cls) -> List["FetchTask"]:
        """
        Generate a list of fetch tasks to be processed by the fetching-plugin.
        """
        currentCommunity = ConfigEntry.getByKey("data.current_community")
        if currentCommunity is None or currentCommunity.value.strip() == "":
            utils.err("Fetching tasks need a current community")
        return [
            cls({
                "type": "members",
                "communitySlug": "hoomans",
                "pageParam": 1,
            }),
            cls({
                "type": "posts",
                "communitySlug": "hoomans",
                "pageParam": 1,
            })
        ]