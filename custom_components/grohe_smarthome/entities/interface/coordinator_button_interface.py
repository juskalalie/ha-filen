from abc import abstractmethod
from typing import Dict


class CoordinatorButtonInterface:
    @abstractmethod
    async def send_command(self, data_to_send: Dict[str, any]) -> Dict[str, any]:
        raise NotImplementedError
