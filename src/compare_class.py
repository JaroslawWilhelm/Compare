import itertools
import time
from collections import Counter

import numpy as np
import pandas as pd

from filter_data import Filter_elements

"""
pandas: FutureWarning: Downcasting behavior in `replace` is deprecated and will be removed in a future version. 
To retain the old behavior, explicitly call `result.infer_objects(copy=False)`. 
To opt-in to the future behavior, set `pd.set_option('future.no_silent_downcasting', True)`
"""
pd.set_option("future.no_silent_downcasting", True)

"""
pandas:
SettingWithCopyWarning: A value is trying to be set on a copy of a slice from a DataFrame
See the caveats in the documentation: https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#returning-a-view-versus-a-copy
"""
pd.options.mode.copy_on_write = True


class CompareElements:
    def __init__(self, dct_dct_dfs1, dct_dct_dfs2, sel_cond):
        self.dct_dct_dfs1 = dict()
        self.dct_dct_dfs2 = dict()
        self.sel_cond = sel_cond

        case_sens = sel_cond[0]
        cut_spases = sel_cond[1]

        if not case_sens or cut_spases:
            for (filename1, file1), (filename2, file2) in zip(
                dct_dct_dfs1.items(), dct_dct_dfs2.items()
            ):
                for dfname, df in file1.items():
                    if not case_sens and cut_spases:
                        df = df.map(str.strip)
                        df = df.map(str.lower)
                        self.dct_dct_dfs1.update({dfname: df})

                    elif case_sens and cut_spases:
                        df = df.map(str.strip)
                        self.dct_dct_dfs1.update({dfname: df})

                    elif not case_sens and not cut_spases:
                        df = df.map(str.lower)
                        self.dct_dct_dfs1.update({dfname: df})

                for dfname, df in file2.items():
                    if not case_sens and cut_spases:
                        df = df.map(str.strip)
                        df = df.map(str.lower)
                        self.dct_dct_dfs2.update({dfname: df})

                    elif case_sens and cut_spases:
                        df = df.map(str.strip)
                        self.dct_dct_dfs2.update({dfname: df})

                    elif not case_sens and not cut_spases:
                        df = df.map(str.lower)
                        self.dct_dct_dfs2.update({dfname: df})

                self.dct_dct_dfs1 = {filename1: self.dct_dct_dfs1}
                self.dct_dct_dfs2 = {filename2: self.dct_dct_dfs2}
        else:
            self.dct_dct_dfs1 = dct_dct_dfs1
            self.dct_dct_dfs2 = dct_dct_dfs2

    @staticmethod
    def same_size(df1, df2, fillvalue):
        zip_shapes = list(zip(df1.shape, df2.shape))
        index, columns = (
            list(range(max(zip_shapes[0]))),
            list(range(max(zip_shapes[1]))),
        )
        df1 = df1.reindex(index=index, columns=columns, fill_value=fillvalue)
        df2 = df2.reindex(index=index, columns=columns, fill_value=fillvalue)
        return df1, df2

    def compare_each_element(self):
        start = time.process_time()
        # import os.path
        # filename1 = os.path.basename(path1)
        # filename2 = os.path.basename(path2)

        arr_concat1 = np.array([])
        arr_concat2 = np.array([])

        try:
            for df in self.dct_dct_dfs1.values():
                arr = df.to_numpy().flatten()
                arr_concat1 = np.concatenate(
                    (arr_concat1, arr), axis=None
                )  # .astype(str)

            for df in self.dct_dct_dfs2.values():
                arr = df.to_numpy().flatten()
                arr_concat2 = np.concatenate(
                    (arr_concat2, arr), axis=None
                )  # .astype(str)

        except:
            for sheet_name, sheet in self.dct_dct_dfs1.items():
                arr_concat1 = pd.concat(sheet).to_numpy().flatten()

            for sheet_name, sheet in self.dct_dct_dfs2.items():
                arr_concat2 = pd.concat(sheet).to_numpy().flatten()

        count1 = Counter(arr_concat1)
        count2 = Counter(arr_concat2)

        del count1[""]
        del count2[""]

        print("count1", len(count1), count1.total())
        print("count2", len(count2), count2.total())
        print()

        onlyIn1 = Counter(
            dict(filter(Filter_elements(count2).is_not_in, count1.items()))
        )
        onlyIn2 = Counter(
            dict(filter(Filter_elements(count1).is_not_in, count2.items()))
        )

        copy_count1 = count1.copy()
        copy_count1.subtract(count2)

        inBoth_sameAmount0 = Counter(
            {key: value for key, value in copy_count1.items() if value == 0}
        )
        # inBoth_sameAmount0 = Counter(dict(filter(Filter_elements().valueIs0, copy_count1.items())))
        # print("in both same ",inBoth_sameAmount0)
        inBoth_sameAmount = Counter(
            dict(filter(Filter_elements(inBoth_sameAmount0).is_in, count2.items()))
        )

        inBoth_diffAmount1 = count1 - inBoth_sameAmount - onlyIn1
        inBoth_diffAmount2 = count2 - inBoth_sameAmount - onlyIn2
        # list_explain1 = [f'in {filename1}, not in {filename2}',
        #                  f'in {filename1}, in both file with different amount',
        #                  'exist in both file with the same amount']
        # list_explain2 = [f'in {filename2}, not in {filename1}',
        #                  f'in {filename2}, in both file with different amount',
        #                  'exist in both file with the same amount']

        list_explain = ["only here", "diff.amount", "same amount"]

        list_searched_data1 = [
            list(onlyIn1),
            list(inBoth_diffAmount1),
            list(inBoth_sameAmount),
        ]
        list_searched_data2 = [
            list(onlyIn2),
            list(inBoth_diffAmount2),
            list(inBoth_sameAmount),
        ]

        def orig_position(dct_dct_dfs, list_searched_data, list_explain):
            dct_result_dfs = dict()
            result_file_name = []
            dct_coord = dict()
            for file_name, dct_dfs in dct_dct_dfs.items():
                for df_name, df in dct_dfs.items():
                    list_coord = []
                    for i in range(3):
                        result_df = df[
                            df.isin(list_searched_data[i])
                        ]  # .dropna(how='all')
                        # coord_for_highlight = np.argwhere(result_df.notna()).tolist()

                        # coords = np.argwhere(result_df.notna()).tolist()
                        # coords = [tuple(coord) for coord in np.argwhere(result_df.notna().values)]
                        coords = list(zip(*np.where(result_df.notna().values)))
                        # coords = [(int(x), int(y)) for x, y in zip(*np.where(result_df.notna().values))]

                        list_coord.append(coords)

                        # result_df.replace("", np.nan, inplace=True)
                        result_df.dropna(how="all", inplace=True)
                        result_df.fillna("", inplace=True)
                        # list_searched_indexes = result_df.index.to_numpy()  # [result_df[all()].notna()].tolist()
                        # print("list searched data in orig pos: ", list_searched_indexes)

                        # list_searched_indexes_incr = list_searched_indexes + 1
                        # result_df.insert(loc=0, column="index", value=list_searched_indexes_incr)

                        # if df_result1.empty:
                        #     df_explain = pd.DataFrame([list_explain[i], 'no elements', ''])
                        # else:
                        #     df_explain = pd.DataFrame([list_explain[i], ''])
                        # df_result2 = pd.concat([df_explain, df_result1], ignore_index=True, axis=0)
                        dct_result_dfs.setdefault(
                            df_name + " " + list_explain[i], result_df
                        )

                    dct_coord.setdefault(df_name, list_coord)

            dct_dct_result_dfs = dict()
            dct_dct_result_dfs.setdefault(file_name + " elem.wise", dct_result_dfs)

            return dct_dct_result_dfs, dct_coord, file_name

            # print("len result_sheets in orig_position ************", len(result_sheets))
            # dct.setdefault("compared", result_sheets)

            # for key1, val1 in dct.items():
            #     print("first loooooop",type(val1), key1)
            #     for key2, val2 in val1.items():
            #         print("second looooooooooop", type(val2), "sheeeeeeeeetsname: ",key2)

        result_dct_dct_dfs1, dct_coord1, file_name1 = orig_position(
            self.dct_dct_dfs1, list_searched_data1, list_explain
        )
        result_dct_dct_dfs2, dct_coord2, file_name2 = orig_position(
            self.dct_dct_dfs2, list_searched_data2, list_explain
        )

        dct_coord1.update(dct_coord2)
        dct_dct_coord1 = dict()
        dct_dct_coord1.setdefault(
            (
                file_name1,
                file_name2,
                " elementwise",
                self.sel_cond[0],
                self.sel_cond[1],
            ),
            dct_coord1,
        )
        end = time.process_time()
        # dct_dct_coord2 = dict()
        # dct_dct_coord2.setdefault((file_name2, file_name1, "elem.wise"), dct_coord2)

        return [
            result_dct_dct_dfs1,
            result_dct_dct_dfs2,
        ], dct_dct_coord1  # , dct_dct_coord2]

    def compare_rowwise(self):
        start = time.process_time()

        # region
        # def take_df_from_dict(dct_dct_dfs1, dct_dct_dfs2):
        #
        #     rows_to_str1 = []
        #     rows_to_str2 = []
        #     dct_dfs_from_rows1 = dict()
        #     dct_dfs_from_rows2 = dict()
        #     dct_dct_dfs_from_rows1 = dict()
        #     dct_dct_dfs_from_rows2 = dict()
        #     dct_labeled_dfs1 = dict()
        #     dct_labeled_dfs2  = dict()
        #     dct_dct_labeled_dfs1 = dict()
        #     dct_dct_labeled_dfs2  = dict()
        #
        #     for (file_name1, dct_dfs1), (file_name2, dct_dfs2) in zip(dct_dct_dfs1.items(), dct_dct_dfs2.items()):
        #         for (sheetname1, sheet1), (sheetname2, sheet2) in zip(dct_dfs1.items(), dct_dfs2.items()):
        #
        #             sheet1, sheet2 = CompareElements.same_size(sheet1, sheet2, None)
        #
        #             # if len(sheet1.index) > len(sheet2.index):
        #             #     sheet2 = sheet2.reindex(index=sheet1.index, columns=sheet2.columns, fill_value="")
        #             # elif len(sheet2.index) > len(sheet1.index):
        #             #     sheet1 = sheet1.reindex(index=sheet2.index, columns=sheet1.columns, fill_value="")
        #             #
        #             # if len(sheet1.columns) > len(sheet2.columns):
        #             #     sheet2 = sheet2.reindex(index=sheet2.index, columns=sheet1.columns, fill_value="")
        #             # elif len(sheet2.columns) > len(sheet1.columns):
        #             #     sheet1 = sheet1.reindex(index=sheet1.index, columns=sheet2.columns, fill_value="")
        #
        #             dct_labeled_dfs1.setdefault(sheetname1, sheet1)
        #             dct_labeled_dfs2.setdefault(sheetname2, sheet2)
        #
        #             str_rows1 = sheet1.apply(lambda row: "".join(map(str, row)), axis=1)
        #             str_rows2 = sheet2.apply(lambda row: "".join(map(str, row)), axis=1)
        #
        #             dct_dfs_from_rows1.setdefault(sheetname1, pd.DataFrame(str_rows1))
        #             dct_dfs_from_rows2.setdefault(sheetname2, pd.DataFrame(str_rows2))
        #
        #             # list_rows1 = list(zip(*[sheet1[col] for col in sheet1]))
        #             # list_rows2 = list(zip(*[sheet2[col] for col in sheet2]))
        #             #
        #             # str_rows1 = [str(el) for el in list_rows1]
        #             # str_rows2 = [str(el) for el in list_rows2]
        #
        #             # dct_dfs_from_rows1.setdefault(sheetname1, pd.DataFrame(str_rows1))
        #             # dct_dfs_from_rows2.setdefault(sheetname2, pd.DataFrame(str_rows2))
        #
        #             rows_to_str1.append(str_rows1)
        #             rows_to_str2.append(str_rows2)
        #
        #         dct_dct_dfs_from_rows1.setdefault(file_name1, dct_dfs_from_rows1)
        #         dct_dct_dfs_from_rows2.setdefault(file_name2, dct_dfs_from_rows2)
        #
        #         dct_dct_labeled_dfs1.setdefault(file_name1, dct_labeled_dfs1)
        #         dct_dct_labeled_dfs2.setdefault(file_name2, dct_labeled_dfs2)
        #
        #         flat_rows1 = list(itertools.chain(*rows_to_str1))
        #         flat_rows2 = list(itertools.chain(*rows_to_str2))
        #
        #     return dct_dct_labeled_dfs1, dct_dct_dfs_from_rows1, flat_rows1, file_name1, dct_dct_labeled_dfs2, dct_dct_dfs_from_rows2, flat_rows2, file_name2
        #
        # dct_dct_labeled_dfs1, dct_dct_dfs_from_rows1, flat_rows1, file_name1, dct_dct_labeled_dfs2, dct_dct_dfs_from_rows2, flat_rows2, file_name2 = take_df_from_dict(self.dct_dct_dfs1, self.dct_dct_dfs2)
        # endregion
        def take_df_from_dict(
            dct_dct_dfs,
        ):
            rows_to_str = []
            dct_dfs_from_rows = dict()
            dct_dct_dfs_from_rows = dict()
            dct_labeled_dfs = dict()
            dct_dct_labeled_dfs = dict()

            for file_name, dct_dfs in dct_dct_dfs.items():
                for sheetname, sheet in dct_dfs.items():
                    # sheet1, sheet2 = CompareElements.same_size(sheet1, sheet2, None)

                    # if len(sheet1.index) > len(sheet2.index):
                    #     sheet2 = sheet2.reindex(index=sheet1.index, columns=sheet2.columns, fill_value="")
                    # elif len(sheet2.index) > len(sheet1.index):
                    #     sheet1 = sheet1.reindex(index=sheet2.index, columns=sheet1.columns, fill_value="")
                    #
                    # if len(sheet1.columns) > len(sheet2.columns):
                    #     sheet2 = sheet2.reindex(index=sheet2.index, columns=sheet1.columns, fill_value="")
                    # elif len(sheet2.columns) > len(sheet1.columns):
                    #     sheet1 = sheet1.reindex(index=sheet1.index, columns=sheet2.columns, fill_value="")

                    # dct_labeled_dfs1.setdefault(sheetname1, sheet1)
                    # dct_labeled_dfs2.setdefault(sheetname2, sheet2)

                    str_rows = sheet.apply(lambda row: "".join(map(str, row)), axis=1)
                    dct_dfs_from_rows.setdefault(sheetname, pd.DataFrame(str_rows))
                    # dct_dfs_from_rows2.setdefault(sheetname2, pd.DataFrame(str_rows2))

                    # list_rows1 = list(zip(*[sheet1[col] for col in sheet1]))
                    # list_rows2 = list(zip(*[sheet2[col] for col in sheet2]))
                    #
                    # str_rows1 = [str(el) for el in list_rows1]
                    # str_rows2 = [str(el) for el in list_rows2]

                    # dct_dfs_from_rows1.setdefault(sheetname1, pd.DataFrame(str_rows1))
                    # dct_dfs_from_rows2.setdefault(sheetname2, pd.DataFrame(str_rows2))

                    rows_to_str.append(str_rows)

                flat_rows = list(itertools.chain(*rows_to_str))

                dct_dct_dfs_from_rows.setdefault(file_name, dct_dfs_from_rows)

            return dct_dct_labeled_dfs, dct_dct_dfs_from_rows, flat_rows, file_name

        dct_dct_labeled_dfs1, dct_dct_dfs_from_rows1, flat_rows1, file_name1 = (
            take_df_from_dict(self.dct_dct_dfs1)
        )

        dct_dct_labeled_dfs2, dct_dct_dfs_from_rows2, flat_rows2, file_name2 = (
            take_df_from_dict(self.dct_dct_dfs2)
        )

        # print("df1 after take df from dict: ", df1)

        # start1 = time.process_time()
        # combined_rows1 = list(zip(*[df1[col] for col in df1]))
        # combined_rows2 = list(zip(*[df2[col] for col in df2]))
        #
        # val_to_str1 = [str(el) for el in combined_rows1]
        # val_to_str2 = [str(el) for el in combined_rows2]
        #
        # df_combined1 = pd.DataFrame(val_to_str1)
        # df_combined2 = pd.DataFrame(val_to_str2)

        # end1 = time.process_time()
        # print("zip ", end1 - start1)

        # start = time.process_time()
        # combined_rows1 = df1.apply(lambda row: "".join(map(str, row)), axis=1)
        # combined_rows2 = df2.apply(lambda row: "".join(map(str, row)), axis=1)
        # end = time.process_time()
        # print("time combined rows: ", end - start)
        # df_combined1 = pd.DataFrame(combined_rows1)
        # df_combined2 = pd.DataFrame(combined_rows2)

        # combined_rows1 = list(zip(*[df1[col] for col in df1]))
        # combined_rows2 = list(zip(*[df2[col] for col in df2]))

        count1 = Counter(flat_rows1)
        count2 = Counter(flat_rows2)

        # del count1['']
        # del count2['']

        onlyIn1 = Counter(
            dict(filter(Filter_elements(count2).is_not_in, count1.items()))
        )
        onlyIn2 = Counter(
            dict(filter(Filter_elements(count1).is_not_in, count2.items()))
        )
        # print("onlys1 ", onlyIn1)
        # print("onlys2 ", onlyIn2)
        copy_count1 = count1.copy()
        copy_count1.subtract(count2)

        inBoth_sameAmount0 = Counter(
            {key: value for key, value in copy_count1.items() if value == 0}
        )
        inBoth_sameAmount = Counter(
            dict(filter(Filter_elements(inBoth_sameAmount0).is_in, count2.items()))
        )
        # print("samis1 ", inBoth_sameAmount)

        inBoth_diffAmount1 = count1 - inBoth_sameAmount - onlyIn1
        inBoth_diffAmount2 = count2 - inBoth_sameAmount - onlyIn2
        # print("diffis ", inBoth_diffAmount1)
        # print("diffis ", inBoth_diffAmount2)
        list_explain = ["only here", "diff.amount", "same amount"]

        # only_df1 = pd.DataFrame(onlyIn1.elements())
        # only_df2 = pd.DataFrame(onlyIn2.elements())
        # diff_amount_df1 = pd.DataFrame(inBoth_diffAmount1.elements())
        # diff_amount_df2 = pd.DataFrame(inBoth_diffAmount2.elements())
        # same_amount_df1 = pd.DataFrame(inBoth_sameAmount.elements())
        #
        # result_dict_df_1 = dict()
        # result_dict_df_1.setdefault(df1_name+" "+"only here", only_df1)
        # result_dict_df_1.setdefault(df1_name + " " + "diff.amount", diff_amount_df1)
        # result_dict_df_1.setdefault(df1_name + " " + "same amount", same_amount_df1)
        #
        # result_dict_df_2 = dict()
        # result_dict_df_2.setdefault(df2_name+" "+"only here", only_df2)
        # result_dict_df_2.setdefault(df2_name + " " + "diff.amount", diff_amount_df2)
        # result_dict_df_2.setdefault(df2_name + " " + "same amount", same_amount_df1)

        #  onlyIn1_tolist = list(chain.from_iterable(onlyIn1))
        #  onlyIn1_del_none = list(filter(None, onlyIn1_tolist))
        #
        #  onlyIn2_tolist = list(chain.from_iterable(onlyIn2))
        #  #print(onlyIn2)
        #  onlyIn2_del_none = list(filter(None, onlyIn2_tolist))
        # # print(onlyIn2)
        #
        #  inBoth_diffAmount1_tolist = list(chain.from_iterable(inBoth_diffAmount1))
        #  inBoth_diffAmount1_del_none = list(filter(None, inBoth_diffAmount1_tolist))
        #
        #  inBoth_diffAmount2_tolist = list(chain.from_iterable(inBoth_diffAmount2))
        #  inBoth_diffAmount2_del_none = list(filter(None, inBoth_diffAmount2_tolist))
        #
        #  inBoth_sameAmount_tolist = list(chain.from_iterable(inBoth_sameAmount))
        #  inBoth_sameAmount_del_none = list(filter(None, inBoth_sameAmount_tolist))

        list_searched_data1 = [onlyIn1, inBoth_diffAmount1, inBoth_sameAmount]
        list_searched_data2 = [onlyIn2, inBoth_diffAmount2, inBoth_sameAmount]

        def orig_position(
            orig_dct_dct_dfs,
            dct_dct_dfs_from_rows,
            list_searched_data,
            list_explain,
            file_name,
        ):
            result_sheets = {}
            dct_coord = dict()
            dct_dct_coord = dict()
            dct_result_dfs = dict()
            dct_dct_result_dfs = dict()

            for (file_name_orig_dfs, orig_dct_dfs), (
                file_name_row_dfs,
                dct_dfs_from_rows,
            ) in zip(orig_dct_dct_dfs.items(), dct_dct_dfs_from_rows.items()):
                for (orig_sheetname, orig_sheet), (
                    sheetname_row_sheet,
                    row_sheet,
                ) in zip(orig_dct_dfs.items(), dct_dfs_from_rows.items()):
                    list_coord = []
                    list_searched_indexes = []
                    for i in range(3):
                        result_sheet = row_sheet[
                            row_sheet.isin(list_searched_data[i].keys())
                        ]

                        result_sheet.dropna(how="all", inplace=True)

                        index_list = result_sheet.index.to_numpy()

                        result_df = orig_sheet.iloc[index_list]

                        res_copy = result_df.replace("", np.nan)
                        df_for_coords = res_copy.reindex_like(orig_sheet)

                        # list_coord.append(np.argwhere(df_for_coords.notna()).tolist())
                        list_coord.append(
                            list(zip(*np.where(df_for_coords.notna().values)))
                        )
                        dct_result_dfs.setdefault(
                            orig_sheetname + " " + list_explain[i], result_df
                        )

                    dct_coord.setdefault(orig_sheetname, list_coord)
                dct_dct_result_dfs.setdefault(
                    file_name_orig_dfs + " rowwise", dct_result_dfs
                )
                # dct_dct_coord.setdefault((file_name_orig_dfs, file_name, "rowwise"), dct_coord)  # update({df_name: list_searched_indexes})

            return dct_dct_result_dfs, dct_coord, file_name_orig_dfs

        dct_dct_result_dfs1, dct_coord1, file_name1 = orig_position(
            self.dct_dct_dfs1,
            dct_dct_dfs_from_rows1,
            list_searched_data1,
            list_explain,
            file_name2,
        )
        dct_dct_result_dfs2, dct_coord2, file_name2 = orig_position(
            self.dct_dct_dfs2,
            dct_dct_dfs_from_rows2,
            list_searched_data2,
            list_explain,
            file_name1,
        )

        dct_coord1.update(dct_coord2)
        dct_dct_coord = dict()
        dct_dct_coord.setdefault(
            (file_name1, file_name2, " rowwise", self.sel_cond[0], self.sel_cond[1]),
            dct_coord1,
        )

        end = time.process_time()

        return [
            dct_dct_result_dfs1,
            dct_dct_result_dfs2,
        ], dct_dct_coord  # , dct_dct_coord2]

    def coordinatewise_sheet_vs_sheet(self):
        start = time.process_time()
        dct_coord1 = dict()
        dct_coord2 = dict()
        dct_dct_coord = dict()
        dct_result_dfs1 = dict()
        dct_result_dfs2 = dict()
        dct_dct_result_dfs1 = dict()
        dct_dct_result_dfs2 = dict()
        for (file_name1, dct_dfs1), (file_name2, dct_dfs2) in zip(
            self.dct_dct_dfs1.items(), self.dct_dct_dfs2.items()
        ):
            for (sheet_name1, sheet1), (sheet_name2, sheet2) in zip(
                dct_dfs1.items(), dct_dfs2.items()
            ):
                list_coord1 = []
                list_coord2 = []

                sheet1, sheet2 = CompareElements.same_size(
                    df1=sheet1, df2=sheet2, fillvalue=None
                )

                diff = sheet1.compare(sheet2, keep_shape=True, keep_equal=False)

                diff.columns = diff.columns.droplevel(0)
                diff = diff.reset_index(drop=True)

                diff1 = diff["self"]
                diff2 = diff["other"]
                diff1 = pd.DataFrame(diff1)
                diff2 = pd.DataFrame(diff2)

                diff1.columns = list(range(len(diff1.columns)))
                diff2.columns = list(range(len(diff2.columns)))
                same = sheet1[~sheet1.isin(diff1)]

                diff1.replace("", np.nan, inplace=True)
                diff2.replace("", np.nan, inplace=True)
                same.replace("", np.nan, inplace=True)

                list_coord1.append(list(zip(*np.where(diff1.notna().values))))
                list_coord2.append(list(zip(*np.where(diff2.notna().values))))
                list_coord1.append(list(zip(*np.where(same.notna().values))))
                list_coord2.append(list(zip(*np.where(same.notna().values))))
                list_coord1.append([])
                list_coord2.append([])

                diff1.dropna(how="all", inplace=True)
                diff2.dropna(how="all", inplace=True)
                same.dropna(how="all", inplace=True)

                diff1.replace(np.nan, "", inplace=True)
                diff2.replace(np.nan, "", inplace=True)
                same.replace(np.nan, "", inplace=True)

                dct_result_dfs1.setdefault(sheet_name1 + " ≠ " + sheet_name2, diff1)
                dct_result_dfs1.setdefault(sheet_name1 + " = " + sheet_name2, same)

                dct_result_dfs2.setdefault(sheet_name2 + " ≠ " + sheet_name1, diff2)
                dct_result_dfs2.setdefault(sheet_name2 + " = " + sheet_name1, same)

                dct_coord1.setdefault(sheet_name1, list_coord1)
                dct_coord2.setdefault(sheet_name2, list_coord2)

            dct_dct_result_dfs1.setdefault(
                file_name1 + " coordinatewise", dct_result_dfs1
            )
            dct_dct_result_dfs2.setdefault(
                file_name2 + " coordinatewise", dct_result_dfs2
            )

        dct_coord1.update(dct_coord2)
        dct_dct_coord.setdefault(
            (
                file_name1,
                file_name2,
                " coordinatewise",
                self.sel_cond[0],
                self.sel_cond[1],
            ),
            dct_coord1,
        )

        end = time.process_time()

        return [dct_dct_result_dfs1, dct_dct_result_dfs2], dct_dct_coord

    def coordinatewise_all_vs_all(self):
        for (file_name1, dct_dfs1), (file_name2, dct_dfs2) in zip(
            self.dct_dct_dfs1.items(), self.dct_dct_dfs2.items()
        ):
            # for (sheet_name1, sheet1 ), (sheet_name2, sheet2) in zip(dct_dfs1.items(), dct_dfs2.items()):

            dct_coord1 = dict()
            dct_coord2 = dict()
            dct_dct_coord = dict()
            dct_result_dfs1 = dict()
            dct_result_dfs2 = dict()
            dct_dct_result_dfs1 = dict()
            dct_dct_result_dfs2 = dict()

            for sheet_name1, sheet1 in dct_dfs1.items():
                for sheet_name2, sheet2 in dct_dfs2.items():
                    list_coord1 = []
                    list_coord2 = []
                    sheet1, sheet2 = CompareElements.same_size(
                        df1=sheet1, df2=sheet2, fillvalue=None
                    )

                    diff = sheet1.compare(
                        sheet2,
                        keep_shape=True,
                    )
                    diff.columns = diff.columns.droplevel(0)
                    diff = diff.reset_index(drop=True)

                    diff1 = diff["self"]
                    diff2 = diff["other"]
                    diff1.columns = list(range(len(diff1.columns)))
                    diff2.columns = list(range(len(diff2.columns)))
                    same = sheet1[~sheet1.isin(diff1)]

                    # diff1.replace("", np.nan, inplace=True)
                    # diff2.replace("", np.nan, inplace=True)
                    # same.replace("", np.nan, inplace=True)

                    list_coord1.append(np.argwhere(diff1.notna()).tolist())
                    list_coord2.append(np.argwhere(diff2.notna()).tolist())
                    list_coord1.append(np.argwhere(same.notna()).tolist())
                    list_coord2.append(np.argwhere(same.notna()).tolist())
                    list_coord1.append([])
                    list_coord2.append([])

                    diff1.dropna(how="all", inplace=True)
                    diff2.dropna(how="all", inplace=True)
                    same.dropna(how="all", inplace=True)

                    # diff1.replace(np.nan, "", inplace=True)
                    # diff2.replace(np.nan, "", inplace=True)
                    # same.replace(np.nan, "", inplace=True)

                    dct_result_dfs1.setdefault(sheet_name1 + " ≠ " + sheet_name2, diff1)
                    dct_result_dfs1.setdefault(sheet_name1 + " = " + sheet_name2, same)

                    dct_result_dfs2.setdefault(sheet_name2 + " ≠ " + sheet_name1, diff2)
                    dct_result_dfs2.setdefault(sheet_name2 + " = " + sheet_name1, same)

                    dct_coord1.setdefault(sheet_name1, list_coord1)
                    dct_coord2.setdefault(sheet_name2, list_coord2)

            dct_dct_result_dfs1.setdefault(
                file_name1 + " coordinatewise", dct_result_dfs1
            )
            dct_dct_result_dfs2.setdefault(
                file_name2 + " coordinatewise", dct_result_dfs2
            )

            dct_coord1.update(dct_coord2)
            dct_dct_coord.setdefault(
                (
                    file_name1,
                    file_name2,
                    " coordinatewise",
                    self.sel_cond[0],
                    self.sel_cond[1],
                ),
                dct_coord1,
            )

            return [dct_dct_result_dfs1, dct_dct_result_dfs2], dct_dct_coord
