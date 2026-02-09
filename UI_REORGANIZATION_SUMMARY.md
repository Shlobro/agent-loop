# UI Reorganization Summary - REVISED

## Major Changes Made

### CRITICAL CHANGE: Two-Column Layout Only
The UI now has a **strict two-column layout**:
- **Left Column**: Tab widget (Logs, Description, Tasks) - only visible when at least one tab is enabled
- **Right Column**: Chat panel ONLY (always visible)

The description preview and task list now ONLY appear in the left tab widget. They never appear above the chat panel on the right side.

## Changes Made

### 1. Removed Control Buttons Row
- **Removed**: The bottom control buttons row containing Start, Pause, Stop, and Next Step buttons
- **Reason**: Consolidate all workflow controls to the menu bar for a cleaner, more streamlined interface
- **Files Modified**:
  - `src/gui/main_window.py`:
    - Removed `control_button_container` and all associated button widgets
    - Removed `on_toggle_control_buttons()` method
    - Removed "Show Control Buttons" action from View menu
    - Updated `_set_debug_waiting()` to use `menu_next_step_button` instead of removed button

### 2. Added Next Step to Menu Bar Icons
- **Added**: Next Step button to the top-right menu bar icon row
- **Location**: Menu bar top-right corner, alongside Start, Pause, and Stop buttons
- **Icon**: SP_ArrowForward (standard Qt icon)
- **Tooltip**: "Next Step (F10)"
- **Files Modified**:
  - `src/gui/main_window.py`: Added `menu_next_step_button` in `_create_workflow_icon_buttons()`
  - Updated `update_button_states()` to control the menu button instead of removed control button

### 3. Created Tabbed Left Panel (REVISED)
- **Implementation**: Left side now uses `QTabWidget` with three independently toggleable tabs
- **Tabs** (all optional, individually controlled):
  1. **Logs**: Original log viewer (toggled via "Show Logs")
  2. **Description**: Description preview - read-only markdown view (toggled via "Show Description")
  3. **Tasks**: Task list with filtering tabs for All/Completed/Incomplete (toggled via "Show Tasks")
- **Behavior**:
  - Each tab can be independently shown/hidden via View menu
  - Left panel only visible when at least one tab is enabled
  - Tabs dynamically added/removed based on which are enabled
  - Right column now contains ONLY the chat panel (no description panel above it)
  - Description content stored in `_description_content` variable instead of UI widget
- **View Menu Items**:
  - "Show Status Panel" - toggles status bar (top)
  - "Show Logs" - toggles Logs tab in left panel
  - "Show Description" - toggles Description tab in left panel
  - "Show Tasks" - toggles Tasks tab in left panel
- **Files Modified**:
  - `src/gui/main_window.py`:
    - Added `left_tab_widget` with three tabs (Logs, Description, Tasks)
    - Added `left_description_preview` (QTextBrowser) for description tab
    - Moved `description_panel` to left tab widget (Tasks tab) - now task-list-only
    - Added `_description_content` to store description separately
    - Added `_get_description()` and `_set_description()` helper methods
    - Added `_sync_description_to_left_preview()` to sync content to preview
    - Added `_update_left_tabs()` to manage tab visibility and dynamic tab addition/removal
    - Added flags: `_logs_enabled`, `_description_enabled`, `_tasks_enabled`
    - Replaced View menu actions with new ones: `show_logs_action`, `show_description_action`, `show_tasks_action`
    - Added handlers: `on_toggle_logs()`, `on_toggle_description()`, `on_toggle_tasks()`
    - Right column layout now only contains `chat_panel` (removed description_panel from right side)
  - `src/gui/settings_mixin.py`:
    - Updated `_set_logs_panel_visible()` to use new `_logs_enabled` flag and call `_update_left_tabs()`

### 4. Added Task Filtering Tabs
- **Implementation**: Task List mode in description panel now uses tabs for filtering
- **Tabs**:
  - **All**: Shows both completed (✓) and incomplete (☐) tasks in a combined view
  - **Completed**: Shows only completed tasks
  - **Incomplete**: Shows only incomplete tasks
- **Visual Format**:
  - All tab: Separates sections with "**Completed:**" and "**Incomplete:**" headers
  - Completed tab: Simple list with "No completed tasks yet." when empty
  - Incomplete tab: Simple list with "No incomplete tasks remaining." when empty
- **Files Modified**:
  - `src/gui/widgets/description_panel.py`:
    - Added `QTabWidget` import
    - Created `task_tabs` widget with three tabs
    - Added `all_tasks_view` (QTextBrowser)
    - Modified `set_tasks()` to populate all three tabs

## Documentation Updates

### Files Updated:
1. `agentHarness_developer_guide.md`: Updated workflow overview to reflect new UI structure
2. `src/gui/gui_developer_guide.md`: Updated menu bar button descriptions and view menu documentation
3. `src/gui/widgets/widgets_developer_guide.md`: Updated description panel and task list documentation

## Testing Notes

All Python files compile successfully without syntax errors:
- ✓ `src/gui/main_window.py`
- ✓ `src/gui/widgets/description_panel.py`
- ✓ `src/gui/settings_mixin.py`

## User-Visible Changes

1. **Two-Column Layout**: Screen always splits into max 2 sections (left tabs, right chat) - nothing ever appears above chat
2. **Cleaner Interface**: Control buttons removed from bottom, reducing visual clutter
3. **Consolidated Controls**: All workflow controls now in consistent locations (menu bar icons + Workflow menu)
4. **Flexible Left Panel**: Users can independently show/hide Logs, Description, and Tasks tabs
5. **Better Task Filtering**: Users can quickly switch between viewing all tasks, only completed, or only incomplete (within Tasks tab)
6. **Space Optimization**: Chat panel always occupies full right column; left panel only shows when needed

## Breaking Changes

- **View Menu**: "Show Control Buttons" action removed (no longer needed)
- **UI Layout**: Bottom button row no longer exists (functionality preserved in menu bar)

## Migration Path

No user action required. Existing workflows continue to work with controls accessible via:
- Menu bar icon buttons (top-right corner)
- Workflow menu items
- Keyboard shortcuts (unchanged)
