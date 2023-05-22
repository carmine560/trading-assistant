def is_running(process):
    """Check if a process is running.

    Args:
        process: name of the process to check

    Returns:
        True if the process is running, False otherwise."""
    import re
    import subprocess

    image = process + '.exe'
    output = subprocess.check_output(['tasklist', '/fi',
                                      'imagename eq ' + image])
    if re.search(image, str(output)):
        return True
    else:
        return False
