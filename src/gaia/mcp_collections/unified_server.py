import argparse
import os
import traceback
from pathlib import Path

from aworld.logs.util import Color
from mcp.server import FastMCP

from src.gaia.mcp_collections.base import ActionArguments
from src.gaia.mcp_collections.documents.mscsv import CSVExtractionCollection
from src.gaia.mcp_collections.documents.msdocx import DOCXExtractionCollection
from src.gaia.mcp_collections.documents.pdf import DocumentExtractionCollection
from src.gaia.mcp_collections.documents.txt import TextExtractionCollection

# Import all collection classes
from src.gaia.mcp_collections.intelligence.code import CodeCollection
from src.gaia.mcp_collections.intelligence.playchess import ChessCollection
from src.gaia.mcp_collections.intelligence.think import ThinkCollection
from src.gaia.mcp_collections.media.audio import AudioCollection
from src.gaia.mcp_collections.media.image import ImageCollection
from src.gaia.mcp_collections.media.video import VideoCollection
from src.gaia.mcp_collections.tools.browser import BrowserCollection
from src.gaia.mcp_collections.tools.download import DownloadCollection
from src.gaia.mcp_collections.tools.mcparxiv import ArxivCollection
from src.gaia.mcp_collections.tools.pubchem import PubChemCollection
from src.gaia.mcp_collections.tools.search import SearchCollection
from src.gaia.mcp_collections.tools.terminal import TerminalCollection
from src.gaia.mcp_collections.tools.wayback import WaybackCollection
from src.gaia.mcp_collections.tools.wiki import WikipediaCollection
from src.gaia.mcp_collections.tools.youtube import YouTubeCollection
from src.gaia.utils import color_log, setup_logger


class UnifiedMCPServer:
    """A Unifined MCP server that integrates all mcp methods from ActionCollections"""

    def __init__(self, arguments: ActionArguments):
        self.arguments = arguments
        self.workspace = self._obtain_valid_workspace(arguments.workspace)
        self.logger = setup_logger("UnifiedMCPServer", self.workspace)

        self.server: FastMCP = FastMCP(arguments.name or "unified-mcp-server")

        self.collections = self._initialize_collections()
        self._register_all_tools()

        self._color_log("Unified MCP Server initialized with all collections", Color.green)
        self._color_log(f"Total tools registered: {len(self.server._tool_manager.list_tools())}", Color.blue)

    def _obtain_valid_workspace(self, workspace: str | None = None) -> Path:
        path = Path(workspace) if workspace else Path(os.getenv("AWORLD_WORKSPACE"))
        if path and path.expanduser().is_dir():
            return path.expanduser().resolve()
        return Path.home().expanduser().resolve()

    def _color_log(self, value: str, color: Color = None, level: str = "info"):
        return color_log(self.logger, value, color, level=level)

    def _initialize_collections(self):
        collection_classes = [
            # Intelligence collections
            CodeCollection,
            ChessCollection,
            ThinkCollection,
            # Document collections
            DocumentExtractionCollection,
            DOCXExtractionCollection,
            CSVExtractionCollection,
            TextExtractionCollection,
            # Media collections
            ImageCollection,
            AudioCollection,
            VideoCollection,
            # Tool collections
            BrowserCollection,
            DownloadCollection,
            SearchCollection,
            TerminalCollection,
            WikipediaCollection,
            WaybackCollection,
            ArxivCollection,
            PubChemCollection,
            YouTubeCollection,
        ]

        collections = []
        for collection_class in collection_classes:
            try:
                collection_args = ActionArguments(
                    name=f"{self.arguments.name}-{collection_class.__name__.lower()}",
                    transport=self.arguments.transport,
                    workspace=self.arguments.workspace,
                    unittest=False,
                )

                collection_instance = collection_class(collection_args)
                collections.append(collection_instance)

                self._color_log(f"Initialized {collection_class.__name__}", Color.cyan, "debug")
            except Exception as e:
                self._color_log(f"Failed to initialize {collection_class.__name__}: {str(e)}", Color.red, "warning")
                self._color_log(f"{traceback.format_exc()}", Color.red, "debug")
        return collections

    def _register_all_tools(self):
        for collection in self.collections:
            for attr_name in dir(collection):
                if attr_name.startswith("mcp_") and callable(getattr(collection, attr_name)):
                    tool_method = getattr(collection, attr_name)

                    collection_name = collection.__class__.__name__.replace("Collection", "").lower()
                    tool_name = f"{collection_name}_{attr_name}"

                    try:
                        self.server.add_tool(
                            tool_method,
                            name=tool_name,
                            description=tool_method.__doc__ or f"Tool from {collection.__class__.__name__}",
                        )

                        self._color_log(f"Registered tool: {tool_name}", Color.blue, "debug")

                    except Exception as e:
                        self._color_log(f"Failed to register {tool_name}: {str(e)}", Color.red, "warning")

    def run(self):
        if not self.arguments.unittest:
            self._color_log("Starting Unified MCP Server...", Color.green)
            if self.arguments.transport == "sse":
                assert self.arguments.port is not None, "Port is required for SSE transport"
                assert type(self.arguments.port) == int, "Port must be a valid integer"
                self.server.settings.port = self.arguments.port
            self.server.run(transport=self.arguments.transport)
        else:
            self._color_log("Running in unittest mode, server not started", Color.yellow)


def main():
    parser = argparse.ArgumentParser(description="Unified MCP Server")
    parser.add_argument("--name", default="unified-mcp-server", help="Server name")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport type")
    parser.add_argument("--port", type=int, help="Server port for SSE transport")
    parser.add_argument("--workspace", help="Workspace directory")
    parser.add_argument("--unittest", action="store_true", help="Run in unittest mode")

    args = parser.parse_args()
    if args.transport == "sse":
        if args.port is None:
            parser.error("--port is required when --transport=sse")
    else:
        if args.port is not None:
            parser.error("--port should not be specified when --transport=stdio")

    os.makedirs(os.getenv("GAIA_WORKSPACE", "/tmp"), exist_ok=True)
    arguments = ActionArguments(
        name="mcp-tools",
        transport="sse",
        port=19090,
        workspace=os.getenv("GAIA_WORKSPACE", "/tmp"),
        unittest=False,
    )

    server = UnifiedMCPServer(arguments)
    server.run()


if __name__ == "__main__":
    main()
