<template>
  <div :class="['form-field', { 'form-field--error': errorMessage, 'form-field--required': required }]">
    <!-- Label -->
    <label v-if="label" :for="fieldId" class="form-field__label">
      {{ label }}
      <span v-if="required" class="form-field__required" aria-hidden="true">*</span>
    </label>

    <!-- Textarea -->
    <textarea
      v-if="type === 'textarea'"
      :id="fieldId"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :rows="rows"
      :class="['form-control', { 'form-control--error': errorMessage }]"
      v-bind="$attrs"
      @input="onInput"
      @blur="onBlur"
    />

    <!-- Select -->
    <select
      v-else-if="type === 'select'"
      :id="fieldId"
      :value="modelValue"
      :disabled="disabled"
      :class="['form-control', { 'form-control--error': errorMessage }]"
      v-bind="$attrs"
      @change="onInput"
      @blur="onBlur"
    >
      <slot />
    </select>

    <!-- Regular input (default) -->
    <div v-else class="form-field__input-wrap">
      <input
        :id="fieldId"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :min="min"
        :max="max"
        :step="step"
        :autocomplete="autocomplete"
        :class="['form-control', { 'form-control--error': errorMessage }]"
        v-bind="$attrs"
        @input="onInput"
        @blur="onBlur"
      />
      <!-- Slot for suffix icons / buttons -->
      <div v-if="$slots.suffix" class="form-field__suffix">
        <slot name="suffix" />
      </div>
    </div>

    <!-- Error message -->
    <p v-if="errorMessage" class="form-field__error" role="alert">
      {{ errorMessage }}
    </p>

    <!-- Help text (shown when no error) -->
    <p v-else-if="helpText" class="form-field__help">
      {{ helpText }}
    </p>
  </div>
</template>

<script>
import { validate } from '@/utils/formValidation'

let _counter = 0

export default {
  name: 'FormField',

  inheritAttrs: false,

  props: {
    /** v-model binding */
    modelValue: {
      default: '',
    },

    /** Label text (omit for no label) */
    label: {
      type: String,
      default: '',
    },

    /** Input type — 'text', 'number', 'password', 'email', 'textarea', 'select' */
    type: {
      type: String,
      default: 'text',
    },

    /** Placeholder text */
    placeholder: {
      type: String,
      default: '',
    },

    /** Gray help text shown below the field (hidden when there is an error) */
    helpText: {
      type: String,
      default: '',
    },

    /** Array of rule functions from formValidation.js */
    rules: {
      type: Array,
      default: () => [],
    },

    /** Show required asterisk next to the label */
    required: {
      type: Boolean,
      default: false,
    },

    /** Disable the field */
    disabled: {
      type: Boolean,
      default: false,
    },

    /** Validate immediately on mount (useful for pre-filled values) */
    validateOnMount: {
      type: Boolean,
      default: false,
    },

    // Pass-through attributes for <input>
    min: { default: undefined },
    max: { default: undefined },
    step: { default: undefined },
    rows: { type: Number, default: 3 },
    autocomplete: { type: String, default: undefined },

    /** Override the error message externally (e.g. from server response) */
    externalError: {
      type: String,
      default: '',
    },
  },

  emits: ['update:modelValue', 'validated'],

  data() {
    return {
      touched: false,
      internalError: '',
      fieldId: `form-field-${++_counter}`,
    }
  },

  computed: {
    errorMessage() {
      return this.externalError || (this.touched ? this.internalError : '')
    },
  },

  mounted() {
    if (this.validateOnMount) {
      this.runValidation(this.modelValue)
    }
  },

  methods: {
    onInput(e) {
      const val = e.target.value
      this.$emit('update:modelValue', this.type === 'number' ? (val === '' ? val : Number(val)) : val)
      if (this.touched) {
        this.runValidation(val)
      }
    },

    onBlur(e) {
      this.touched = true
      this.runValidation(e.target.value)
    },

    runValidation(value) {
      const result = validate(value, this.rules)
      this.internalError = result === true ? '' : result
      this.$emit('validated', { valid: result === true, error: this.internalError })
    },

    /** Call this externally to force validation (e.g. on form submit). */
    touch() {
      this.touched = true
      this.runValidation(this.modelValue)
      return this.internalError === '' && !this.externalError
    },

    /** Reset validation state. */
    reset() {
      this.touched = false
      this.internalError = ''
    },
  },
}
</script>

<style scoped>
.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0;
}

/* Label */
.form-field__label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary, #1e293b);
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.form-field__required {
  color: #ef4444;
  font-weight: 700;
  line-height: 1;
}

/* Input wrapper for suffix slot */
.form-field__input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.form-field__input-wrap .form-control {
  flex: 1;
}

.form-field__suffix {
  position: absolute;
  right: 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  pointer-events: none;
}

/* Error styling applied to the native input/select/textarea */
.form-control--error {
  border-color: #ef4444 !important;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.15) !important;
}

.form-control--error:focus {
  border-color: #ef4444 !important;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2) !important;
}

/* Error / help text */
.form-field__error {
  font-size: 0.78rem;
  color: #ef4444;
  margin: 0;
  line-height: 1.4;
  display: flex;
  align-items: flex-start;
  gap: 0.25rem;
}

.form-field__error::before {
  content: '⚠';
  font-size: 0.75rem;
  flex-shrink: 0;
  margin-top: 0.05rem;
}

.form-field__help {
  font-size: 0.78rem;
  color: var(--text-secondary, #64748b);
  margin: 0;
  line-height: 1.4;
}
</style>
