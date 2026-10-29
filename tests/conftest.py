def centered_scroll(tree):
    height = tree.scrollable_content_region.height
    return max(0, min(max(0, tree.last_line + 1 - height), tree.cursor_line - (height - 1) // 2))
