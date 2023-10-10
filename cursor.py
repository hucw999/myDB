from common import *

def leaf_node_find(table, page_num, key):
    node = table.pager.get_page(page_num)
    cell_nums = get_leaf_num_cells(node)
    l = 0
    r = cell_nums
    cursor = Cursor(table)
    cursor.page_num = page_num
    while l != r:
        mid = int((l+r) / 2)
        print(l,r,mid)
        mid_key = node[leaf_node_cell(mid):leaf_node_cell(mid)+LEAF_NODE_KEY_SIZE].decode('utf-8')
        
        if mid_key == key:
            cursor.cell_num = mid
            return cursor
        elif mid_key > key:
            r = mid 
        else:
            l = mid + 1
    cursor.cell_num = l
    print('cursor.cell_num', cursor.cell_num)
    return cursor

def internal_node_find(table, page_num, key):
    node = table.pager.get_page(page_num)
    num_keys = get_internal_node_num_keys(node)
    cursor = Cursor(table)
    cursor.page_num = page_num

    l = 0
    r = num_keys
    while l < r:
        mid = int((l+r) / 2)
        mid_key = internal_node_key(node, mid)
        if mid_key >= key:
            r = mid
        else:
            l = mid + 1
    child_num = internal_node_child(node, l)
    child_node = table.pager.get_page(child_num)
    if get_node_type(child_node) == NodeType.NODE_INTERNAL.value:
        return internal_node_find(table, child_num, key)
    else:
        return leaf_node_find(table, child_num, key)
        

class Cursor():
    def __init__(self, table) -> None:
        self.table = table
        self.end_of_table = False
        self.page_num = 0
        self.cell_num = 0

    def get_value(self):
        page_num = self.page_num
        print(f'pnum:{page_num}')
        
        return self.table.pager.get_page(page_num)[LEAF_NODE_VALUE_OFFSET:LEAF_NODE_VALUE_OFFSET+LEAF_NODE_VALUE_SIZE]

    def advance(self):
        page = self.table.pager.get_page(self.page_num)
        self.cell_num += 1
        num_cells = get_leaf_num_cells(page)
        if self.cell_num >= num_cells:
            next_page_num = get_leaf_node_next_leaf(page)
            if next_page_num == 0:
                self.end_of_table = True
            else:
                self.page_num= next_page_num
                self.cell_num = 0

    def leaf_node_insert(self, key, value):
        node = self.table.pager.get_page(self.page_num)
        num_cells = get_leaf_num_cells(node)
        if num_cells >= LEAF_NODE_MAX_CELLS:
            self.leaf_node_split_insert(key, value)
            return
            # raise Exception(f'Too many cells found {num_cells}')
        if self.cell_num < num_cells:
            print('debug0')
            index = num_cells
            while index > self.cell_num:
                node[leaf_node_cell(index):leaf_node_cell(index)+LEAF_NODE_CELL_SIZE] = node[leaf_node_cell(index-1):leaf_node_cell(index-1)+LEAF_NODE_CELL_SIZE]
                index -= 1
        b_key = bytearray(key.encode('utf-8'))
        node[leaf_node_cell(self.cell_num):leaf_node_cell(self.cell_num)+len(b_key)] = b_key
        serialize_row(value, node, leaf_node_value(self.cell_num))
        num_cells += 1
        node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = num_cells.to_bytes(LEAF_NODE_NUM_CELLS_SIZE, 'little')

    def leaf_node_split_insert(self, key, value):
        old_node = self.table.pager.get_page(self.page_num)
        new_page_num = get_unused_page_num(self.table.pager)
        new_node = self.table.pager.get_page(new_page_num)
        initialize_leaf_node(new_node)
        old_next_page_num = get_leaf_node_next_leaf(old_node)
        new_node[LEAF_NODE_NEXT_LEAF_OFFSET:LEAF_NODE_NEXT_LEAF_OFFSET+LEAF_NODE_NEXT_LEAF_SIZE] = (old_next_page_num).to_bytes(LEAF_NODE_NEXT_LEAF_SIZE, 'little')
        old_node[LEAF_NODE_NEXT_LEAF_OFFSET:LEAF_NODE_NEXT_LEAF_OFFSET+LEAF_NODE_NEXT_LEAF_SIZE] = (new_page_num).to_bytes(LEAF_NODE_NEXT_LEAF_SIZE, 'little')

        for i in range(LEAF_NODE_MAX_CELLS, -1, -1):
            print(f'i: {i}')
            index_within_node = i % LEAF_NODE_LEFT_SPLIT_COUNT
            if i >= LEAF_NODE_LEFT_SPLIT_COUNT:
                dest_node = new_node
            else:
                dest_node = old_node
            if i == self.cell_num:
                b_key = bytearray(key.encode('utf-8'))
                dest_node[leaf_node_cell(index_within_node):leaf_node_cell(index_within_node)+len(b_key)] = b_key
                serialize_row(value, dest_node, leaf_node_value(index_within_node))
                
            elif i > self.cell_num:
                dest_node[leaf_node_cell(index_within_node):leaf_node_cell(index_within_node)+LEAF_NODE_CELL_SIZE] \
                    = old_node[leaf_node_cell(i-1):leaf_node_cell(i-1)+LEAF_NODE_CELL_SIZE]
            else:
                print(i, leaf_node_cell(i))
                dest_node[leaf_node_cell(index_within_node):leaf_node_cell(index_within_node)+LEAF_NODE_CELL_SIZE] \
                    = old_node[leaf_node_cell(i):leaf_node_cell(i)+LEAF_NODE_CELL_SIZE]
            
        old_node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = LEAF_NODE_LEFT_SPLIT_COUNT.to_bytes(LEAF_NODE_NUM_CELLS_SIZE, 'little')
        new_node[LEAF_NODE_NUM_CELLS_OFFSET:LEAF_NODE_NUM_CELLS_OFFSET+LEAF_NODE_NUM_CELLS_SIZE] = LEAF_NODE_RIGHT_SPLIT_COUNT.to_bytes(LEAF_NODE_NUM_CELLS_SIZE, 'little')
        if old_node[IS_ROOT_OFFSET:IS_ROOT_OFFSET+IS_ROOT_SIZE] == (1).to_bytes(IS_ROOT_SIZE, 'little'):
            print('debug2')
            return create_new_root(self.table, new_page_num)
