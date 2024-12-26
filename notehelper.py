import io
import os.path

import asciidoc
import logging
import jaro


logger = logging.getLogger(__name__)


def text_2_html(text_in):
    # print("convert asciidoc text")
    text_out = io.StringIO()
    test = asciidoc.AsciiDocAPI()
    test.execute(io.StringIO(text_in), text_out, backend="html5")
    return text_out.getvalue()

def search_files(search_text, files, project_path, cut_off=0.8):
    logger.info("search files")
    jaro_filenames_result = []
    jaro_results = []
    for file in files:
        jaro_file_metric = jaro.jaro_winkler_metric(file, search_text)
        if jaro_file_metric >= cut_off or search_text in file and file not in jaro_filenames_result:
            jaro_filenames_result.append(file)
        file_path = os.path.join(project_path, file)
        try:
            with open(file_path, "r") as file_search:
                file_text = file_search.read()
        except Exception as e:
            logger.error("error {} searching file {}".format(e, file))
            file_text = ""
        jaro_metric = jaro.jaro_winkler_metric(search_text, file_text)
        if jaro_metric >= cut_off or search_text in file_text and file not in jaro_filenames_result:
            jaro_results.append(file)
    logger.info("creating result page")
    result_text = "== result search for \"{}\"".format(search_text)
    result_text = "{}\n\n=== search text found in filename".format(result_text)
    for single_result in jaro_filenames_result:
        result_text = "{}\n* link:{}[{}]".format(result_text, single_result, single_result)
    result_text = "{}\n\n=== search text found in files".format(result_text)
    for single_result in jaro_filenames_result:
        result_text = "{}\n* link:{}[{}]".format(result_text, single_result, single_result)
    result_text = "{}\n\n".format(result_text)
    return result_text


if __name__ == "__main__":
    print("moin")
