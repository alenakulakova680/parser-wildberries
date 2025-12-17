import pytest

from unittest.mock import patch, Mock
from parsermain import the_cheapest, sorted_data, save_to_csv
from unittest.mock import mock_open, patch, Mock

class TestTheCheapest:
    def test_find_cheapest_product(self):
        """Тест 1: Находим самый дешевый товар"""
        products = [
            [1001, 5000, "Товар A", "4.5"],
            [1002, 3000, "Товар B", "4.7"],  
            [1003, 7000, "Товар C", "4.9"],
            "timestamp"  
        ]
        
        result = the_cheapest(products)
        
        assert result is not None
        assert result[0] == 1002  
        assert result[1] == 3000  
        assert result[2] == "Товар B"
    
    def test_empty_product_list(self):
        empty_list = []
        result = the_cheapest(empty_list)

        assert result is None
    
    def test_only_timestamp_in_list(self):
        data = ["timestamp"]
        result = the_cheapest(data)

        assert result is None

class TestSortedData:    

    def test_sort_basic_list(self):
        test_data = [
            [333, 7000, "Товар C", "4.8"],
            [111, 5000, "Товар A", "4.0"],
            [222, 3000, "Товар B", "4.5"]
        ]
        result = sorted_data(test_data)
        assert len(result) == 3
        
        assert result[0][0] == 111 
        assert result[1][0] == 222
        assert result[2][0] == 333

    def test_remove_duplicates(self):
        test_data = [
            [111, 5000, "Товар A", "4.0"],
            [222, 3000, "Товар B", "4.5"],
            [111, 5500, "Товар A другой", "4.2"],  
            [333, 7000, "Товар C", "4.8"],
            [222, 3200, "Товар B новый", "4.6"]  
        ]
        result = sorted_data(test_data)
        assert len(result) == 3  
        assert result[0][0] == 111
        assert result[0][1] == 5000
        assert result[1][0] == 222
        assert result[1][1] == 3000

    def test_with_duplicates_only(self):
        test_data = [
            [111, 5000, "Товар A", "4.0"],
            [111, 5500, "Товар A другой", "4.2"],
            [111, 6000, "Товар A третий", "4.5"]
        ]
        result = sorted_data(test_data)
        assert len(result) == 1

    def test_none_data(self):
        with pytest.raises(Exception):
            sorted_data(None)
    
    def test_invalid_structure(self):

        invalid_data = [
            [111],  
            [222, 3000],  
            "текст"  
        ]
        with pytest.raises(Exception):
            sorted_data(invalid_data)

class TestSaveToCSV:
    def test_save_csv_basic_mock(self):

        test_data = [
            [123, 1000, "Телефон", "4.5"],
            [456, 2000, "Ноутбук", "4.8"]
        ]
        
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('csv.writer') as mock_writer_class:
                with patch('datetime.datetime') as mock_datetime:
                    
                    mock_writer = Mock()
                    mock_writer_class.return_value = mock_writer
                    mock_datetime.now.return_value.strftime.return_value = "01.01.2024 12:00:00"

                    save_to_csv(test_data, 1, 777) 
                    assert mock_file.called
                    assert mock_file.call_args[0][0] == 'elements_777_1.csv'
                    assert mock_writer.writerow.call_count == 3 

def test_save_csv_error_mock():
    test_data = [[111, 500, "Товар", "5.0"]]
    with patch('builtins.open') as mock_open_error:
        mock_open_error.side_effect = PermissionError("Нет прав на запись")
        try:
            save_to_csv(test_data, 3, 999)
            assert False
        except PermissionError:
            assert True