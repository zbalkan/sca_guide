from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Button, Header, Input, Label, Static, TextArea


class PolicyEditScreen(Static):

    DEFAULT_CSS = """
    PolicyEdit{
        layout: grid;
        grid-size: 6 5;
        grid-gutter: 1 2;
        grid-columns: 1fr;
        grid-rows: 1fr 1fr 2fr 2fr 1fr;
        height: 100%;
    }
    Input,TextArea{
        column-span: 5;
    }
    #save{

    }
    #discard{

    }
    """

    originalTitle: str
    originalDesc: str

    def __init__(self, originalTitle: str, originalDesc: str) -> None:
        self.originalTitle = originalTitle
        self.originalDesc = originalDesc
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label("Original Title")
        yield Input(self.originalTitle, disabled=True)
        yield Label("New Title")
        yield Input()
        yield Label("Original Description")
        yield TextArea(self.originalDesc, disabled=True)
        yield Label("New Description")
        yield TextArea()
        yield Label()
        yield Button("Save", id="save", variant="success")
        yield Button("Discard", id="discard", variant="error")


class ScaGuideApp(App):
    """A Textual app to help creating a custom Wazuh SCA."""

    originalTitle: str
    originalDesc: str

    def updatePolicy(self, originalTitle: str, originalDesc: str) -> None:
        self.originalTitle = originalTitle
        self.originalDesc = originalDesc

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield ScrollableContainer(PolicyEditScreen(originalTitle=self.originalTitle, originalDesc=self.originalDesc))

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark
