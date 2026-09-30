def autoname(doc, method):
	"""Name as '<code system> <code value>', e.g. 'ICD-10 Z94.4'. Runs after healthcare's autoname."""
	doc.name = f"{doc.code_system} {doc.code_value}"
