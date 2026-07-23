# SN PPT Workbench User Guide

This guide is for users who generate, inspect, edit, and export PPT decks with SenseNova-Skills. PPT Workbench uses `/progress` for generation progress and `/editor` for the editor. The root path `/` redirects to the appropriate page based on generation status.

## Use Top-Bar Tools: Language, Appearance, Notifications, and Agent Status

The top-right area contains the language button, appearance button, notification bell, and Agent status button. The language button switches between Simplified Chinese and English. The appearance button supports system, light, and dark modes. The notification bell collects export, error, and background-task messages. The Agent status shows whether the current workbench is managed by the Agent.

![Top-bar tools](images/agent-webui/topbar-utilities.jpg)

## Generate a PPT

If you want to generate a presentation from a topic, materials, or research results and watch the progress while it runs, describe the topic, audience, slide count, style, and whether you need the WebUI directly in the conversation. For example:

```text
Create an 8-slide Chinese PPT about enterprise AI Agent adoption paths for executives. Use a clean business style. Start the WebUI during generation and provide the progress-page URL.
```

The Agent prepares the task pack and information pack. After the WebUI starts, it replies with an address similar to the one below:

![PPT WebUI starts and returns an address](images/agent-webui/ppt-workbench-init.jpg)

After opening this address, the left pane shows the slide list, the middle pane shows the latest generated slide or JSON artifact, and the right pane shows the stage timeline and Agent process messages. The page syncs automatically, so you do not need to refresh it repeatedly.

![PPT generation progress overview](images/agent-webui/ppt-progress-overview.jpg)

When the top status shows “Generating” or “Completed,” the WebUI is connected to the current task. If the right pane keeps showing `task_pack.json`, `info_pack.json`, `outline.json`, or slide-generation messages, the generation process is moving forward. If there are no new messages for a long time, ask the Agent to check the background process and `.workbench/progress.json`.

During generation, you do not need to wait until the full deck is complete before checking the output. Once a slide has been generated, the corresponding item in the left slide list can be opened.

![Open a generated slide](images/agent-webui/ppt-progress-unlocked-slide.jpg)

If you have not manually clicked any slide or file, the middle area automatically displays the latest generated artifact. Once you manually select a slide or file, the WebUI keeps your selection and will not jump away when later artifacts are generated. The right pane usually shows a “Follow latest” entry that restores automatic following.

### Enter the PPT Editor and Understand the Layout

After PPT generation is complete, the progress page provides a “generation complete, enter editor” link. You can also open the editor address under the same port:

![PPT generation completes and provides the PPT editor page address](images/agent-webui/ppt-editor-init.jpg)

The PPT editor is used to inspect results, fine-tune pages, continue revising the PPT through Agent chat, and export the final file. The editor top bar contains the title, generation status, page navigation, language, appearance, notifications, and Agent status.
- The left pane is the page or file pane, the middle pane is the slide preview, and the right pane is the AI chat pane.

The second toolbar contains undo, redo, reset, save, export, download assets, present, copy, delete, select, rectangle select, lasso select, text, image, and the page/file/chat pane toggles.

![PPT editor overview](images/agent-webui/ppt-editor-overview.jpg)

If you need the Agent to check structure, style consistency, factual risk, or page-level issues, the bottom of the right chat pane provides “Analyze deck” and “Analyze current page.” “Analyze current page” is suitable for single-slide wording, layout, and readability. “Analyze deck” is suitable for cross-slide narrative, style consistency, missing assets, and structural issues.

Analysis results are shown by severity, such as “High,” “Medium,” and “Low.” Each finding usually includes a description, affected pages, evidence, and an actionable button. Handle high-severity findings first, then review medium and low-severity items. If a suggestion does not fit your delivery goal, you can ignore it.

### Select Slide Elements

If you only want to modify a title, shape, text block, or image instead of asking the Agent to rewrite the whole slide, select the target element on the canvas first.

1. Choose “Select” from the second toolbar.
2. Click the target element on the canvas.
3. To select multiple elements, use “Rectangle select” or “Lasso select.”

![Select a slide element](images/agent-webui/ppt-select-element.webp)

### Drag, Resize, and Edit Text

After an element is selected, an object toolbar appears near the middle canvas. It shows the element type, position, size, fill color, text color, and actions such as edit text, bring to front, send to back, and alignment. You can drag the element directly or adjust position and size through the toolbar.

![Drag and resize an element](images/agent-webui/ppt-drag-resize-element.webp)

After dragging or resizing, the save, undo, and redo states in the top toolbar update accordingly. Make a small adjustment first, check the result, then click “Save.” If you are only experimenting, use “Undo” to go back. Before switching slides, save or undo unsaved changes so you do not forget the current state.

### Ask the Agent to Modify Selected Elements

After selecting an element, a prompt such as “1 element selected” appears above the chat box. Requests in the right chat box then include the selected-element context. If no selection appears after clicking, the current page may not declare editable regions, or the clicked position may not be a selectable element.

Once an element is selected, you can ask the Agent to modify only that part. Before sending, confirm that “1 element selected” is still shown above the chat box, then describe the scope clearly. For example:

```text
Only optimize the selected title element so the wording is more suitable for an executive presentation. Do not change its position or font size.
```

![Select an element and send an instruction to the Agent](images/agent-webui/ppt-chat-selected-element.webp)

If you need reference files, add them with the attachment button before sending the instruction. Be explicit about scope and constraints, such as “only change the wording, not the position or font size,” to reduce unintended layout changes.

### Use Presentation Mode

To check the presentation experience or rehearse before delivery, click “Present” in the second toolbar. Click an empty area of the slide to go to the next page, or use keyboard arrows, PageUp/PageDown, or the mouse wheel to move between pages. Links, videos, and other interactive elements keep their own click behavior. Press `Esc` or use the presentation toolbar to exit.

![PPT presentation mode](images/agent-webui/ppt-presentation-mode.webp)

If the presentation toolbar auto-hides, move the mouse to show it again. Presentation mode enters full screen by default. The full-screen toggle is near the page navigation buttons and can be changed during presentation.

### Export to PPTX, PDF, or Images

To export to PPTX, PDF, or images, click “Export” in the second toolbar, choose PPTX, PDF, or image format from the menu, and the file starts downloading immediately after confirmation.

![PPT export menu](images/agent-webui/ppt-export-menu.webp)

If you choose PPTX, the system shows a compatibility notice because HTML-to-PPTX conversion may still have font-size, chart, or layout differences. If layout fidelity is critical, also use “Download assets” to keep the full HTML asset package, or export PDF as a stable delivery version.

### View PPT Files and Asset Previews

To check whether page HTML, JSON planning files, images, and scripts exist, or to debug resource loading, click “File” on the right side of the second toolbar. The left pane switches from the slide list to the file pane. Click files such as `pages/page_001.html`, `outline.json`, or `style_spec.json`; the middle area shows the file path as the title and renders or highlights the file content. Click the download button in the file pane to package and download all files.

![PPT file pane and preview](images/agent-webui/ppt-file-pane-preview.webp)

The file pane and page pane are mutually exclusive. If images do not load, first check whether the corresponding asset exists in the file pane, then check whether the HTML reference path matches the asset directory.
