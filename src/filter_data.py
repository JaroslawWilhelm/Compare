from load_dfs import *


class Filter_elements:
    def __init__(self, data=None):
        self.data = data

    # def sameAmount(self, data2):
    #
    #     key, value = data2
    #     if value == 0:
    #         return True
    #     else:
    #         return False

    # def rename_none(self, data):
    #     for ind, el in enumerate(data):
    #         if el == 'nan' or el == '':
    #             data[ind] = '0:0'
    #
    #     return data
    def rows_is_not_in(self, pair):
        key, value = pair
        if value not in self.data.values():
            return True
        else:
            return False

    def rows_is_in(self, pair):
        key, value = pair
        if value in self.data.values():
            return True
        else:
            return False

    def is_not_in(self, pair):
        key, value = pair

        if key not in self.data:
            return True
        else:
            return False

    def is_in(self, pair):
        key, value = pair
        if key in self.data:
            return True
        else:
            return False

    def valueIs0(self, pair):
        key, value = pair
        if value == 0:
            return True
        else:
            return False


# filt = Filter_Counts
# writer2 = pd.ExcelWriter(r"/home/xxx-anonym-xxx/Schreibtisch/test2.xlsx")
# for sheetname, df in df2.items():
#     df.style.map(lambda v: 'background-color:gold;' if v in list(onlyIn2) else None) \
#         .map(lambda v: 'background-color:yellow;' if v in list(notSameAmount2) else None) \
#         .to_excel(writer2, sheet_name=sheetname,
#                   index=False, header=False)

# df_prity.to_excel(writer1, index=False, header=False)
# writer1._save()

# writer2 = pd.ExcelWriter(r"/home/xxx-anonym-xxx/Schreibtisch/test2.xlsx")
# for sheetname, df in df2.items():
#     (df.style.map(lambda v: 'background-color:gold;' if v in list(onlyIn2) else 'background-color:yellow;' if v in list(notSameAmount2) else None)
#      .to_excel(writer2, sheet_name=sheetname,
#                   index=False, header=False))
# writer2._save()
