def write_to_file(*, filename, content, append=False):
    """Write content to a file with option to append or overwrite.

    Args:
        filename (str): Name of the file to write to
        content: Content to write (string, list, or any object with __str__)
        append (bool): If True, append to existing file; if False, overwrite (default: False)
    """
    mode = "a" if append else "w"
    with open(filename, mode) as file:
        # Handle different types of content
        if isinstance(content, (list, tuple)):
            file.writelines([str(item) + "\n" for item in content])
        else:
            file.write(str(content) + "\n")
