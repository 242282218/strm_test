import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fileManagerApi, type FileItem } from '../api/file-manager'

export const useFileManagerStore = defineStore('fileManager', () => {
    // 状态
    const currentPath = ref('0') // 夸克默认以 '0' 为根
    const parentPath = ref<string | null>(null)
    const currentStorage = ref<'local' | 'quark'>('quark')
    const items = ref<FileItem[]>([])
    const total = ref(0)
    const loading = ref(false)
    const viewMode = ref<'grid' | 'list'>('grid')
    const selectedIds = ref<Set<string>>(new Set())

    // 分页
    const page = ref(1)
    const pageSize = ref(100)

    // 计算属性
    const isAllSelected = computed(() => {
        return items.value.length > 0 && selectedIds.value.size === items.value.length
    })

    const selectedItems = computed(() => {
        return items.value.filter(item => selectedIds.value.has(item.id))
    })

    // 动作
    async function browse(path: string = currentPath.value, storage = currentStorage.value) {
        loading.value = true
        try {
            currentPath.value = path
            currentStorage.value = storage
            const res = await fileManagerApi.browse({
                storage,
                path,
                page: page.value,
                size: pageSize.value
            })
            items.value = res.data.items
            total.value = res.data.total
            parentPath.value = res.data.parent_path
            selectedIds.value.clear()
        } catch (error) {
            console.error('Failed to browse directory:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    function toggleSelection(id: string) {
        if (selectedIds.value.has(id)) {
            selectedIds.value.delete(id)
        } else {
            selectedIds.value.add(id)
        }
    }

    function selectAll() {
        items.value.forEach(item => selectedIds.value.add(item.id))
    }

    function clearSelection() {
        selectedIds.value.clear()
    }

    async function deleteSelected() {
        if (selectedIds.value.size === 0) return

        const paths = Array.from(selectedIds.value) // 夸克中使用 ID 作为路径标识
        try {
            await fileManagerApi.operation({
                action: 'delete',
                storage: currentStorage.value,
                paths
            })
            await browse() // 刷新
        } catch (error) {
            console.error('Failed to delete items:', error)
            throw error
        }
    }

    async function moveItems(targetPath: string) {
        if (selectedIds.value.size === 0) return

        const paths = Array.from(selectedIds.value)
        try {
            await fileManagerApi.operation({
                action: 'move',
                storage: currentStorage.value,
                paths,
                target: targetPath
            })
            selectedIds.value.clear()
            await browse()
        } catch (error) {
            console.error('Failed to move items:', error)
            throw error
        }
    }

    return {
        currentPath,
        parentPath,
        currentStorage,
        items,
        total,
        loading,
        viewMode,
        selectedIds,
        isAllSelected,
        selectedItems,
        browse,
        toggleSelection,
        selectAll,
        clearSelection,
        deleteSelected,
        moveItems
    }
})
