# Virtual Revision NVDA plugin
#Copyright (C) 2012-2020 Rui Batista and contributors
#Copyright (C) 2021-2023 Rui Fontes, Rui Batista and contributors
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import globalPluginHandler
import globalVars
import api
import textInfos
import ui
import scriptHandler
import addonHandler
addonHandler.initTranslation()

try:
	from globalCommands import SCRCAT_TEXTREVIEW
except:
	SCRCAT_TEXTREVIEW = None

def _isTermControl(obj):
	return hasattr(obj, "UIAElement") and obj.UIAElement and obj.UIAElement.currentClassName == "TermControl"

def _isDecorativeTerminalLine(line):
	# True for lines whose only non-whitespace characters are in the Unicode Box Drawing
	# block (U+2500-U+257F): the borders, separators, and corners that TUI apps such as
	# Claude Code paint. Content lines that happen to contain a "│" border still survive
	# because the letters/digits inside fall outside the range.
	stripped = line.strip()
	if not stripped:
		return True
	return all("─" <= ch <= "╿" for ch in stripped)

def _cleanTerminalText(text):
	# Terminal cells are space-padded to the column width, and TUI apps reserve fixed
	# rows/columns for borders, status, input, etc. Captured as a UNIT_STORY this turns
	# into long runs of blank padding and box-border-only lines that bury the actual
	# content when navigated line-by-line in the review window. Strip per-line trailing
	# whitespace and drop lines that carry no real content.
	lines = []
	for line in text.split("\n"):
		stripped = line.rstrip()
		if _isDecorativeTerminalLine(stripped):
			continue
		lines.append(stripped)
	return "\n".join(lines)

def obtainUWPWindowText():
	foreground = api.getForegroundObject()
	desktop = api.getDesktopObject()
	uwpTextList = [foreground.name]
	termTextList = []
	hasTerm = _isTermControl(foreground)
	curObject=foreground.firstChild
	while curObject:
		if _isTermControl(curObject):
			hasTerm = True
			info = curObject.makeTextInfo(textInfos.POSITION_FIRST)
			info.expand(textInfos.UNIT_STORY)
			termTextList.append(_cleanTerminalText(info.clipboardText))
		elif curObject.name is not None:
			uwpTextList.append(curObject.name)
		if curObject.simpleFirstChild:
			curObject=curObject.simpleFirstChild
			continue
		if curObject.simpleNext:
			curObject=curObject.simpleNext
			continue
		if curObject.simpleParent:
			parent=curObject.simpleParent
			# As long as one is on current foreground object...
			# Stay within the current top-level window.
			if parent.simpleParent == desktop:
				break
			while parent and not parent.simpleNext:
				parent=parent.simpleParent
			# But sometimes, the top-level window has no sibling at all (such is the case in Windows 10 Start menu).
			try:
				curObject=parent.simpleNext
			except AttributeError:
				continue
	if _isTermControl(foreground):
		hasTerm = True
		info = foreground.makeTextInfo(textInfos.POSITION_FIRST)
		info.expand(textInfos.UNIT_STORY)
		termTextList.append(_cleanTerminalText(info.clipboardText))
	# For terminal-hosted windows (e.g. cmd.exe inside Windows Terminal), the child walk
	# also picks up the duplicated title, scroll-bar parts, "Close Tab" and "System" menu.
	# Suppress that chrome and return only the title plus the actual terminal text.
	if hasTerm:
		return [foreground.name] + termTextList
	return uwpTextList

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	scriptCategory = SCRCAT_TEXTREVIEW

	@scriptHandler.script(
		# Translators: Message presented in input help mode.
		description=_("Opens a window containing the text of the currently focused window for easy review."),
		gesture="kb:nvda+control+w"
	)
	def script_virtualWindowReview(self, gesture):
		# Find the first focus ancestor that have any display text, according to the display model
		# This must be the root application window, or something close to that.
		# In case of universal apps, traverse child elements.
		text = None
		obj = api.getFocusObject()
		# Because it may take a while to iterate through elements, play abeep to alert users of this fact and the fact it's a UWP screen.
		if obj.windowClassName.startswith(("Windows.UI.Core", "Windows.UI.Input.InputSite")):
			import tones
			tones.beep(400, 300)
			text = "\n".join(obtainUWPWindowText())
			tones.beep(400, 50)
		else:
			root = None
			for ancestor in api.getFocusAncestors():
				if ancestor.appModule and ancestor.displayText:
					root = ancestor
					break
			if root:
				info = root.makeTextInfo(textInfos.POSITION_FIRST)
				# sys.maxint is gone in Python 3 as integer bit width can grow arbitrarily.
				# Use the static value (0x7fffffff or (2^31)-1) directly.
				info.move(textInfos.UNIT_LINE, 0x7fffffff, endPoint="end")
				text = info.clipboardText.replace("\0", " ")
			if obj.windowClassName == u'ConsoleWindowClass':
				info = obj.makeTextInfo(textInfos.POSITION_FIRST)
				info.expand(textInfos.UNIT_STORY)
				text = info.clipboardText.rstrip()
		if text:
			name = api.getForegroundObject().name
			if name in (None, ""):
				# Translators: The title of the virtual review window when the foreground window has no name, commonly seen when all windows are minimized.
				name = _("No title")
			# Translators: Title of the window shown for reading text on screen via a window.
			ui.browseableMessage(text, title=_("Virtual review: {screenName}").format(screenName = name))
		else:
			# Translator: Message shown when no text can be virtualized.
			ui.message(_("No text to display"))


# Avoid use on secure screens
if globalVars.appArgs.secure:
	# Override the global plugin to disable it.
	GlobalPlugin = globalPluginHandler.GlobalPlugin
