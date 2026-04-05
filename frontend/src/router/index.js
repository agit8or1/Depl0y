import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/vms',
      name: 'VirtualMachines',
      component: () => import('@/views/VirtualMachines.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/vms/create',
      name: 'CreateVM',
      component: () => import('@/views/CreateVM.vue'),
      meta: { requiresAuth: true, requiresOperator: true }
    },
    {
      path: '/deploy',
      name: 'Deploy',
      component: () => import('@/views/Deploy.vue'),
      meta: { requiresAuth: true, requiresOperator: true }
    },
    {
      path: '/import-vm',
      name: 'ImportVM',
      component: () => import('@/views/ImportVM.vue'),
      meta: { requiresAuth: true, requiresOperator: true }
    },
    {
      path: '/llm-deploy',
      name: 'DeployLLM',
      component: () => import('@/views/DeployLLM.vue'),
      meta: { requiresAuth: true, requiresOperator: true }
    },
    {
      path: '/vms/:id',
      name: 'VMDetails',
      component: () => import('@/views/VMDetails.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/vm-management',
      name: 'VMManagement',
      component: () => import('@/views/VMManagement.vue'),
      meta: { requiresAuth: true, requiresOperator: true }
    },
    {
      path: '/proxmox',
      name: 'ProxmoxHosts',
      component: () => import('@/views/ProxmoxHosts.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/images',
      name: 'Images',
      component: () => import('@/views/Images.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/isos',
      redirect: '/images'
    },
    {
      path: '/cloud-images',
      redirect: '/images'
    },
    {
      path: '/ha-management',
      name: 'HAManagement',
      component: () => import('@/views/HAManagement.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/users',
      name: 'Users',
      component: () => import('@/views/Users.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/Settings.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/documentation',
      name: 'Documentation',
      component: () => import('@/views/Documentation.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/about',
      name: 'About',
      component: () => import('@/views/About.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/bug-report',
      name: 'BugReport',
      component: () => import('@/views/BugReport.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/support',
      name: 'Support',
      component: () => import('@/views/Support.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/linux-vms',
      name: 'LinuxVMManagement',
      component: () => import('@/views/LinuxVMManagement.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/security',
      name: 'Security',
      component: () => import('@/views/Security.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/idrac',
      name: 'IDracManagement',
      component: () => import('@/views/IDracManagement.vue'),
      meta: { requiresAuth: true, requiresOperator: true }
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound.vue')
    }
  ]
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Initialize auth if not already done
  if (!authStore.isAuthenticated && localStorage.getItem('access_token')) {
    await authStore.initializeAuth()
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
  } else if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next('/')
  } else if (to.meta.requiresOperator && !authStore.isOperator) {
    next('/')
  } else {
    next()
  }
})

export default router
