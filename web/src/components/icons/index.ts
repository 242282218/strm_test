/**
 * 图标统一管理模块
 * 按需导出项目中使用的所有图标，避免全局注册导致的打包体积过大
 */

// 布局相关图标
export {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Cloudy,
  Expand,
  Fold,
  Moon,
  Sunny,
  UserFilled
} from '@element-plus/icons-vue'

// 导航菜单图标
export {
  Odometer,
  Search,
  MagicStick,
  FolderOpened,
  Document,
  CollectionTag,
  Monitor,
  Link,
  Folder,
  List,
  Setting,
  Film,
  VideoPlay,
  Tools,
  Bell,
  Message,
  ChatDotSquare,
  House
} from '@element-plus/icons-vue'

// 操作相关图标
export {
  Plus,
  Refresh,
  RefreshRight,
  Delete,
  Edit,
  Check,
  Warning,
  InfoFilled,
  CircleCheck,
  CircleClose,
  Promotion,
  Download,
  Star,
  Filter,
  Collection,
  Calendar,
  Clock,
  Grid,
  VideoCamera,
  VideoPause,
  DocumentAdd,
  DocumentChecked,
  HomeFilled,
  FolderAdd,
  Upload,
  Cpu,
  User,
  Lock
} from '@element-plus/icons-vue'

// 图标名称到组件的映射表（用于动态图标）
import type { Component } from 'vue'
import {
  Odometer,
  Search,
  MagicStick,
  FolderOpened,
  Document,
  CollectionTag,
  Monitor,
  Link,
  Folder,
  List,
  Setting,
  Film,
  VideoPlay,
  Tools,
  Bell,
  Message,
  ChatDotSquare,
  House,
  Refresh,
  Check,
  ArrowRight
} from '@element-plus/icons-vue'

export const iconMap: Record<string, Component> = {
  Odometer,
  Search,
  MagicStick,
  FolderOpened,
  Document,
  CollectionTag,
  Monitor,
  Link,
  Folder,
  List,
  Setting,
  Film,
  VideoPlay,
  Tools,
  Bell,
  Message,
  ChatDotSquare,
  House,
  Refresh,
  Check,
  ArrowRight
}

/**
 * 根据图标名称获取图标组件
 * @param name 图标名称
 * @returns 图标组件或 undefined
 */
export function getIconComponent(name: string): Component | undefined {
  return iconMap[name]
}
