"""Tests for Lathe PDF processing operations."""

import pytest

from lathe.pdf_ops import _parse_page_range, extract_text, get_info, merge


class TestPdfInfo:
    def test_returns_page_count(self, sample_pdf):
        info = get_info(sample_pdf)
        assert info["page_count"] == 1

    def test_returns_file_size(self, sample_pdf):
        info = get_info(sample_pdf)
        assert info["file_size"] > 0

    def test_returns_title_metadata(self, sample_pdf):
        info = get_info(sample_pdf)
        assert info["title"] == "Test PDF"

    def test_returns_author_metadata(self, sample_pdf):
        info = get_info(sample_pdf)
        assert info["author"] == "Lathe Tests"

    def test_not_encrypted(self, sample_pdf):
        info = get_info(sample_pdf)
        assert info["encrypted"] is False


class TestPdfExtractText:
    def test_extracts_text_content(self, sample_pdf):
        result = extract_text(sample_pdf)
        assert "Hello from Lathe PDF test" in result["text"]
        assert result["method"] == "text_layer"
        assert result["char_count"] > 0

    def test_pages_extracted_list(self, sample_pdf):
        result = extract_text(sample_pdf)
        assert result["pages_extracted"] == [1]

    def test_with_page_range(self, sample_pdf):
        result = extract_text(sample_pdf, pages="1")
        assert result["pages_extracted"] == [1]
        assert result["char_count"] > 0


class TestPdfMerge:
    def test_merge_two_pdfs(self, two_sample_pdfs, tmp_path):
        out = tmp_path / "merged.pdf"
        result = merge(two_sample_pdfs, out)
        assert result["input_count"] == 2
        assert result["total_pages"] == 2
        assert out.exists()
        assert result["output_size"] > 0

    def test_merged_pdf_readable(self, two_sample_pdfs, tmp_path):
        from pypdf import PdfReader

        out = tmp_path / "merged.pdf"
        merge(two_sample_pdfs, out)
        reader = PdfReader(out)
        assert len(reader.pages) == 2


class TestParsePageRange:
    def test_none_returns_all(self):
        assert _parse_page_range(None, 5) == [0, 1, 2, 3, 4]

    def test_single_page(self):
        assert _parse_page_range("1", 5) == [0]

    def test_single_page_last(self):
        assert _parse_page_range("5", 5) == [4]

    def test_range(self):
        assert _parse_page_range("1-3", 5) == [0, 1, 2]

    def test_range_clamped_to_total(self):
        # "1-10" on a 3-page doc should return [0, 1, 2]
        assert _parse_page_range("1-10", 3) == [0, 1, 2]

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            _parse_page_range("10", 3)

    def test_malformed_raises(self):
        with pytest.raises(ValueError):
            _parse_page_range("abc", 3)

    def test_whitespace_stripped(self):
        assert _parse_page_range("  2  ", 5) == [1]
