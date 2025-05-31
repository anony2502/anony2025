import re, warnings
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava
from .logger import logger

warnings.filterwarnings("ignore")
JAVA_LANGUAGE = Language(tsjava.language(), "java")
parser = Parser()
parser.set_language(JAVA_LANGUAGE)

# public  static -> public static
def get_text(node):
    if node is None:
        return ""
    text = node.text.decode().strip()
    return re.sub(r"\s+", " ", text)

def traverse_tree(tree):
    cursor = tree.walk()
    visited_children = False
    while True:
        if not visited_children:
            yield cursor.node
            if not cursor.goto_first_child():
                visited_children = True
        elif cursor.goto_next_sibling():
            visited_children = False
        elif not cursor.goto_parent():
            break

def find_comments(node):
    if "comment" in node.type:
        yield node.start_byte, node.end_byte
    else:
        for child in node.children:
            yield from find_comments(child)


def get_code_without_comments(code_str: str) -> str:
    code_bytes = code_str.encode()
    tree = parser.parse(code_bytes)
    comments = list(find_comments(tree.root_node))
    res_bytes = b""
    start = 0
    for comment in comments:
        res_bytes += code_bytes[start : comment[0]]
        # add 1 to skip the \n
        start = comment[1] + 1
    res_bytes += code_bytes[start:]
    return res_bytes.decode().strip()


def filter_code(code_str: str, clean_comments=False) -> str:
    """
    Filter the given code string by removing comments and cleaning up whitespace.

    Args:
        code_str (str): The code string to filter.
        clean_comments (bool, optional): Whether to remove comments from the code. Defaults to False.

    Returns:
        str: The filtered code string.
    """
    if clean_comments:
        code_str = get_code_without_comments(code_str)
    code_str = code_str.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    code_str = re.sub(" +", " ", code_str)
    return code_str.strip()


def extract_method_from_line(file_str: str, sig_line: int) -> str:
    """
    Extracts the source code of a method from a given file string based on any line number of the method.

    Args:
        file_str (str): The content of the file as a string.
        sig_line (str): Any line number of signature(index from 0).

    Returns:
        str: The source code of the method as a string.

    """
    tree = parser.parse(bytes(file_str, "utf8"))
    method_node = None
    for node in list(traverse_tree(tree)):
        if node.type == "method_declaration" or node.type == "constructor_declaration":
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            if sig_line >= start_line and sig_line <= end_line:
                method_node = node
                return method_node.text.decode()
    logger.warning(f"Method with line number: #{sig_line} not found in file.")
    return ""

def extract_class_from_line(file_str: str, sig_line: int) -> str:
    """
    Extracts the source code of a class from a given file string based on any line number of the class.

    Args:
        file_str (str): The content of the file as a string.
        sig_line (str): Any line number of signature(index from 0).

    Returns:
        str: The source code of the class as a string.

    """
    tree = parser.parse(bytes(file_str, "utf8"))
    method_node = None
    for node in list(traverse_tree(tree)):
        if node.type == "class_declaration" or node.type == "enum_declaration" or node.type == "interface_declaration":
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            if sig_line >= start_line and sig_line <= end_line:
                method_node = node
                return method_node.text.decode()
    logger.warning(f"Class with line number: #{sig_line} not found in file.")
    return ""

def extract_class_varibles(code_str: str) -> list[str]:
    tree = parser.parse(bytes(code_str, "utf8"))
    root_node = tree.root_node
    
    variables = []
    
    def traverse(node):
        if node.type == "field_declaration":
            variables.append(node.text.decode())
        for child in node.children:
            traverse(child)
    
    traverse(root_node)
    print(variables)
    return variables