import os
import zipfile
from PyPDF2 import PdfMerger
import shutil


def merge_pdfs(pdf_files, output_path):
    print("Merging PDFs: ", pdf_files, " -to- ", output_path)
    pdf_merger = PdfMerger()

    for pdf_file in pdf_files:
        with open(pdf_file, 'rb') as pdf_file:
            pdf_merger.append(pdf_file)

    with open(output_path, 'wb') as output_pdf:
        pdf_merger.write(output_pdf)


def process_zip(zip_file, output_folder, delete_zips=False):
    try:
        print("Processing: ", zip_file)
        book_name = os.path.basename(zip_file).split('.')[0].strip()
        temp_extract_folder = os.path.join(output_folder, f"temp_{book_name}")

        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_folder)

        pdf_files = []
        for root, _, files in os.walk(temp_extract_folder):
            for file in files:
                if file.endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))

        pdf_files.insert(0, pdf_files.pop())

        output_pdf_path = os.path.join(output_folder, f"{book_name}.pdf")
        merge_pdfs(pdf_files, output_pdf_path)

        # Clean up the intermediate extracted files
        shutil.rmtree(temp_extract_folder, ignore_errors=True)

        if delete_zips:
            os.remove(zip_file)
        print("Done processing: ", zip_file, "\n\n")
    except Exception as e:
        print("Failed to process: ", zip_file, e)
        shutil.rmtree(os.path.join(output_folder, f"temp_{book_name}"), ignore_errors=True)


def merge_and_cleanup_zip_files(zip_folder, delete_zips):
    for root, _, files in os.walk(zip_folder):
        for file in files:
            if file.endswith('.zip'):
                zip_file_path = os.path.join(root, file)
                process_zip(zip_file_path, root, delete_zips)

if __name__ == "__main__":
    # Replace with the path to the folder containing the zip files
    zip_folder_path = "downloads"
    # Whether to delete the original zips after merging pdfs
    delete_zips = True
    merge_and_cleanup_zip_files(zip_folder_path, delete_zips)
