<template>
  <div 
    class="appointment-card cursor-pointer transition-all duration-200 hover:shadow-md w-full h-full rounded-md border border-dotted group"
    :class="cardStyleClasses"
    @click="$emit('click', appointment)"
  >
    <div class="p-1 h-full flex flex-col">
      <!-- Patient Name -->
      <div class="flex-shrink-0 mb-1">
        <h4 class="text-xs font-bold leading-tight break-words" :class="textColorClasses">
          {{ appointment.patient_name || 'Unknown Patient' }}
        </h4>
      </div>
      
      <!-- Compact Info Section -->
      <div class="flex flex-col space-y-0.5">
        <!-- Insurance Company -->
        <div class="flex items-start flex-shrink-0" :class="textColorClasses">
          <FeatherIcon name="shield" class="h-2 w-2 mr-1 flex-shrink-0 mt-0.5" />
          <span class="text-2xs font-semibold leading-tight break-words" style="font-size: 10px;">{{ appointment.insurance_company || 'Cash' }}</span>
        </div>
        
        <!-- Billing Item -->
        <div v-if="appointment.billing_item" class="flex items-start flex-shrink-0" :class="textColorClasses">
          <FeatherIcon name="file-text" class="h-2 w-2 mr-1 flex-shrink-0 mt-0.5" />
          <span class="text-2xs font-semibold leading-tight break-words" style="font-size: 10px;">{{ appointment.billing_item }}</span>
        </div>
        
        <!-- Paid Amount / Item Rate -->
        <div class="flex items-start flex-shrink-0" :class="textColorClasses">
          <FeatherIcon name="dollar-sign" class="h-2 w-2 mr-1 flex-shrink-0 mt-0.5" />
          <span class="text-2xs font-semibold leading-tight" style="font-size: 10px;">{{ formatAmount(appointment.paid_amount || appointment.item_rate || 0) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { FeatherIcon, Badge, Button, Tooltip } from 'frappe-ui'
import dayjs from 'dayjs'

const props = defineProps({
  appointment: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['click', 'complete', 'cancel'])

// Status-based styling
const cardStyleClasses = computed(() => {
  const baseClasses = 'shadow-sm'
  
  switch (props.appointment.status) {
    case 'open':
      return `${baseClasses} bg-yellow-200 border-yellow-500 hover:bg-yellow-300`
    case 'completed':
    case 'closed':
      return `${baseClasses} bg-green-200 border-green-500 hover:bg-green-300`
    case 'scheduled':
      return `${baseClasses} bg-orange-200 border-orange-500 hover:bg-orange-300`
    case 'cancelled':
      return `${baseClasses} bg-red-200 border-red-500 hover:bg-red-300`
    default:
      return `${baseClasses} bg-gray-200 border-gray-400 hover:bg-gray-300`
  }
})

// Get text color based on status for better contrast
const textColorClasses = computed(() => {
  switch (props.appointment.status) {
    case 'open':
      return 'text-yellow-900'
    case 'completed':
    case 'closed':
      return 'text-green-900'
    case 'scheduled':
      return 'text-orange-900'
    case 'cancelled':
      return 'text-red-900'
    default:
      return 'text-gray-900'
  }
})

const getStatusTheme = (status) => {
  const themeMap = {
    open: 'yellow',
    completed: 'green',
    closed: 'green',
    scheduled: 'orange',
    cancelled: 'red'
  }
  return themeMap[status] || 'gray'
}

// Helper functions
const formatTime = (timeSlot) => {
  return dayjs(`2024-01-01 ${timeSlot}`).format('h:mm A')
}

const formatStatus = (status) => {
  const statusMap = {
    open: 'Open',
    completed: 'Completed',
    closed: 'Closed',
    scheduled: 'Scheduled',
    cancelled: 'Cancelled'
  }
  return statusMap[status] || status
}

const formatAmount = (amount) => {
  if (!amount || amount === 0) return 'TZS 0'
  return `TZS ${Number(amount).toLocaleString()}`
}
</script>

<style scoped>
.appointment-card {
  min-height: 100%;
}
</style>
