import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Mail, FileText, Warehouse, Settings2, Edit, RotateCcw, Eye, Save, X, AlertCircle, CheckCircle, MapPin, Building2, CreditCard, Users, Server, Copy, Package, Box, Plus, Trash2, Sparkles } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

// Sedes disponibles
const SEDES = [
  { id: 'PYME', name: 'Pyme', shortName: 'Pyme' },
  { id: 'CORP', name: 'Corp', shortName: 'Corp' }
];

// Tipos base de plantillas (sin sede)
const BASE_TEMPLATE_TYPES = [
  {
    baseId: 'quote_sent',
    icon: Mail,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    title: 'Envío de Cotización a Cliente',
    description: 'Se envía al cliente cuando se genera una cotización'
  },
  {
    baseId: 'quote_approved',
    icon: CheckCircle,
    color: 'text-emerald-600',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    title: 'Cotización Aprobada',
    description: 'Se envía cuando una cotización es aprobada'
  },
  {
    baseId: 'invoice',
    icon: FileText,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    title: 'Facturación y Control Contable',
    description: 'Se envía a Administración cuando se factura'
  },
  {
    baseId: 'warehouse',
    icon: Warehouse,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    title: 'Despacho de Equipos',
    description: 'Se envía a Almacén cuando equipos son pagados'
  },
  {
    baseId: 'implementation',
    icon: Settings2,
    color: 'text-cyan-600',
    bgColor: 'bg-cyan-50',
    borderColor: 'border-cyan-200',
    title: 'Envío a Implementación',
    description: 'Se envía a Implementación con detalles técnicos'
  },
  {
    baseId: 'repair_invoice',
    icon: FileText,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    title: 'Facturación de Reparaciones',
    description: 'Se envía a Ventas cuando se factura una reparación de equipos'
  },
  {
    baseId: 'payment_receipt',
    icon: CheckCircle,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    title: 'Envío de Comprobante de Pago',
    description: 'Notifica a Ventas que el cliente pagó para enviar a Implementación'
  },
  {
    baseId: 'fast_track_approved',
    icon: Settings2,
    color: 'text-violet-600',
    bgColor: 'bg-violet-50',
    borderColor: 'border-violet-200',
    title: 'Aprobación de Cotización MPOS (Imple + POS)',
    description: 'Se envía al aprobar cotización MPOS (Imple + POS)'
  },
  {
    baseId: 'serial_preassignment',
    icon: Box,
    color: 'text-cyan-600',
    bgColor: 'bg-cyan-50',
    borderColor: 'border-cyan-200',
    title: 'Preasignación de Seriales',
    description: 'Notifica al Almacén la reserva de seriales para una cotización'
  }
];

// Plantillas de Equipos (separadas por sede PYME/CORP)
const EQUIPMENT_TEMPLATE_TYPES = [
  {
    baseId: 'equipment_sent',
    icon: Mail,
    color: 'text-sky-600',
    bgColor: 'bg-sky-50',
    borderColor: 'border-sky-200',
    title: 'Envío de Cotización de Equipos a Clientes',
    description: 'Se envía al cliente con la propuesta económica de equipos'
  },
  {
    baseId: 'equipment_approved',
    icon: CheckCircle,
    color: 'text-teal-600',
    bgColor: 'bg-teal-50',
    borderColor: 'border-teal-200',
    title: 'Aprobación de Cotización de Equipos',
    description: 'Se envía a Administración al aprobar cotización de equipos'
  },
  {
    baseId: 'equipment_invoice',
    icon: FileText,
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
    borderColor: 'border-indigo-200',
    title: 'Facturación de Equipos',
    description: 'Se envía cuando se carga la factura de venta de equipos'
  },
  {
    baseId: 'equipment_collect',
    icon: CreditCard,
    color: 'text-rose-600',
    bgColor: 'bg-rose-50',
    borderColor: 'border-rose-200',
    title: 'Envío de Comprobante de Pago de Equipos',
    description: 'Se envía al recibir el soporte de pago por compra de equipos'
  },
  {
    baseId: 'equipment_delivery',
    icon: Warehouse,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    title: 'Orden de Entrega de Equipos',
    description: 'Se envía a Logística para preparar y despachar los equipos'
  }
];

// Plantillas globales de Proyecto (no se dividen por sede)
const PROJECT_TEMPLATE_TYPES = [
  {
    templateId: 'new_integration_project',
    icon: Mail,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    title: 'Nuevo Proyecto de Integracion',
    description: 'Se envia al Gerente de Implementacion al crear un nuevo proyecto de integracion'
  },
  {
    templateId: 'project_notify_client',
    icon: Mail,
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    title: 'Notificacion de Proyecto — Cliente',
    description: 'Comunicaciones secuenciales al cliente durante implementacion'
  },
  {
    templateId: 'project_notify_bank',
    icon: Mail,
    color: 'text-teal-600',
    bgColor: 'bg-teal-50',
    borderColor: 'border-teal-200',
    title: 'Notificacion de Proyecto — Banco',
    description: 'Comunicaciones secuenciales a bancos durante implementacion'
  },
  {
    templateId: 'project_notify_bank_client',
    icon: Mail,
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
    borderColor: 'border-indigo-200',
    title: 'Notificacion de Proyecto Banco y Cliente',
    description: 'Notifica simultaneamente al Banco y al Cliente cuando el proyecto tiene un solo banco'
  }
];

// Generar configuración de plantillas por sede
const generateTemplateConfig = () => {
  const config = {};
  SEDES.forEach(sede => {
    BASE_TEMPLATE_TYPES.forEach(template => {
      const templateId = `${template.baseId}_${sede.id}`;
      config[templateId] = {
        ...template,
        title: `${template.title} (Sede ${sede.shortName})`,
        sede: sede.id,
        sedeName: sede.name
      };
    });
    EQUIPMENT_TEMPLATE_TYPES.forEach(template => {
      const templateId = `${template.baseId}_${sede.id}`;
      config[templateId] = {
        ...template,
        title: `${template.title} (${sede.shortName})`,
        sede: sede.id,
        sedeName: sede.name
      };
    });
  });
  return config;
};

const TEMPLATE_CONFIG = generateTemplateConfig();

// Variables disponibles por tipo de plantilla (aplican a todas las sedes)
const BASE_TEMPLATE_VARIABLES = {
  quote_sent: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'company_name', label: 'Nombre de la Empresa' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  quote_approved: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'approved_date', label: 'Fecha de Aprobación' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  invoice: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'invoice_number', label: 'Número de Factura' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_invoice: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'invoice_number', label: 'Número de Factura' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  warehouse: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'client_address', label: 'Dirección del Cliente' },
    { key: 'items_table', label: 'Tabla de Items' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  implementation: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'integrator_name', label: 'Nombre del Integrador' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'services_table', label: 'Tabla de Servicios' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  payment_receipt: [
    { key: 'quote_number', label: 'Número de Cotización' },
    { key: 'client_name', label: 'Nombre del Cliente' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'total_usd', label: 'Total USD' },
    { key: 'sede_name', label: 'Nombre de la Sede' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  fast_track_approved: [
    { key: 'Cotizacion_Nro', label: 'Número de Cotización' },
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente' },
    { key: 'Rif_Cliente', label: 'RIF del Cliente' },
    { key: 'Monto_Total', label: 'Monto Total USD' },
    { key: 'Modelo_Equipo', label: 'Modelo de POS / PINPAD' },
    { key: 'Cantidad', label: 'Cantidad de Equipos' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  serial_preassignment: [
    { key: 'Cotizacion_Nro', label: 'Número de Cotización' },
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente' },
    { key: 'Modelo_Equipo', label: 'Modelo de Equipo' },
    { key: 'Lista_Seriales', label: 'Lista de Seriales Preasignados' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_quote_sent: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'modelos_resumen', label: 'Resumen de Modelos' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_approved: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_complete_client: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'lista_modelos_seriales', label: 'Lista de Modelos y Seriales' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  repair_delivery: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'contacto_cliente', label: 'Contacto del Cliente' },
    { key: 'tipo_nota_entrega', label: 'Tipo de Entrega (Parcial/Final)' },
    { key: 'nro_nota_entrega', label: 'Nro. Nota de Entrega' },
    { key: 'cantidad_entregada', label: 'Cantidad Entregada' },
    { key: 'estatus_entrega', label: 'Estatus de Entrega' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' }
  ],
  repair_collect_warehouse: [
    { key: 'nro_cotizacion', label: 'Nro. de Cotización' },
    { key: 'nombre_cliente', label: 'Nombre del Cliente' },
    { key: 'lista_equipos_seriales', label: 'Lista de Equipos y Seriales' },
    { key: 'almacen_custodia', label: 'Almacén de Custodia' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  // === Plantillas de Equipos (Ventas) ===
  equipment_sent: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente' },
    { key: 'Cotizacion_Nro', label: 'Número de Cotización' },
    { key: 'Monto_Total', label: 'Monto Total USD' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  equipment_approved: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente' },
    { key: 'Rif_Cliente', label: 'RIF del Cliente' },
    { key: 'Cotizacion_Nro', label: 'Número de Cotización' },
    { key: 'Monto_Total', label: 'Monto Total USD' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  equipment_invoice: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente' },
    { key: 'Cotizacion_Nro', label: 'Número de Cotización' },
    { key: 'Referencia_Factura', label: 'Referencia de Factura' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  equipment_collect: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente' },
    { key: 'Rif_Cliente', label: 'RIF del Cliente' },
    { key: 'Cotizacion_Nro', label: 'Número de Cotización' },
    { key: 'Monto_Total', label: 'Monto Total USD' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  equipment_delivery: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente' },
    { key: 'Rif_Cliente', label: 'RIF del Cliente' },
    { key: 'Cotizacion_Nro', label: 'Número de Cotización' },
    { key: 'Direccion_Entrega', label: 'Dirección de Entrega' },
    { key: 'items_table', label: 'Tabla de Equipos (HTML)' },
    { key: 'Nombre_Ejecutivo', label: 'Nombre del Ejecutivo' },
    { key: 'Email_Ejecutivo', label: 'Email del Ejecutivo' }
  ],
  // === Plantillas de Notificaciones de Proyectos (Implementación) ===
  project_notify_client: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente (Razón Social)' },
    { key: 'Contacto_Principal', label: 'Contacto Principal del Cliente' },
    { key: 'Nombre_Sucursal', label: 'Nombre de Sucursal(es)' },
    { key: 'Cantidad_Cajas', label: 'Cantidad de Cajas (PDVs)' },
    { key: 'Integrador', label: 'Integrador Asignado' },
    { key: 'Aplicativo_Integracion', label: 'Aplicativo de Integración' },
    { key: 'Nombre_Implementador', label: 'Nombre del Implementador' },
    { key: 'Correo_Implementador', label: 'Correo del Implementador' },
    { key: 'Telefono_Implementador', label: 'Teléfono del Implementador' },
    { key: 'Matriz_Bancos_Productos', label: 'Tabla de Bancos y Productos (HTML)' },
    { key: 'project_number', label: 'Nro. de Proyecto' },
    { key: 'quote_number', label: 'Nro. de Cotización' },
    { key: 'ticket_number', label: 'Nro. de Ticket' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'notification_level', label: 'Nivel de Notificación' },
    { key: 'notification_subject', label: 'Asunto de Notificación' },
    { key: 'assigned_to', label: 'Asignado a' },
  ],
  project_notify_bank: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente (Razón Social)' },
    { key: 'Contacto_Principal', label: 'Contacto Principal del Cliente' },
    { key: 'Nombre_Sucursal', label: 'Nombre de Sucursal(es)' },
    { key: 'Cantidad_Cajas', label: 'Cantidad de Cajas (PDVs)' },
    { key: 'Integrador', label: 'Integrador Asignado' },
    { key: 'Aplicativo_Integracion', label: 'Aplicativo de Integración' },
    { key: 'Nombre_Implementador', label: 'Nombre del Implementador' },
    { key: 'Correo_Implementador', label: 'Correo del Implementador' },
    { key: 'Telefono_Implementador', label: 'Teléfono del Implementador' },
    { key: 'Matriz_Bancos_Productos', label: 'Tabla de Bancos y Productos (HTML)' },
    { key: 'bank_name', label: 'Nombre del Banco' },
    { key: 'bank_products', label: 'Productos del Banco' },
    { key: 'project_number', label: 'Nro. de Proyecto' },
    { key: 'quote_number', label: 'Nro. de Cotización' },
    { key: 'ticket_number', label: 'Nro. de Ticket' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'integrator_app_name', label: 'Aplicativo del Integrador' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'notification_level', label: 'Nivel de Notificación' },
    { key: 'notification_subject', label: 'Asunto de Notificación' },
  ],
  project_notify_bank_client: [
    { key: 'Nombre_Cliente', label: 'Nombre del Cliente (Razón Social)' },
    { key: 'Contacto_Principal', label: 'Contacto Principal del Cliente' },
    { key: 'Nombre_Sucursal', label: 'Nombre de Sucursal(es)' },
    { key: 'Cantidad_Cajas', label: 'Cantidad de Cajas (PDVs)' },
    { key: 'Integrador', label: 'Integrador Asignado' },
    { key: 'Aplicativo_Integracion', label: 'Aplicativo de Integración' },
    { key: 'Nombre_Implementador', label: 'Nombre del Implementador' },
    { key: 'Correo_Implementador', label: 'Correo del Implementador' },
    { key: 'Telefono_Implementador', label: 'Teléfono del Implementador' },
    { key: 'Matriz_Bancos_Productos', label: 'Tabla de Bancos y Productos (HTML)' },
    { key: 'bank_name', label: 'Nombre del Banco' },
    { key: 'bank_products', label: 'Productos del Banco' },
    { key: 'project_number', label: 'Nro. de Proyecto' },
    { key: 'quote_number', label: 'Nro. de Cotización' },
    { key: 'ticket_number', label: 'Nro. de Ticket' },
    { key: 'client_rif', label: 'RIF del Cliente' },
    { key: 'quote_type', label: 'Tipo de Cotización' },
    { key: 'integrator_app_name', label: 'Aplicativo del Integrador' },
    { key: 'pinpad_model', label: 'Modelo de Pinpad' },
    { key: 'notification_level', label: 'Nivel de Notificación' },
    { key: 'notification_subject', label: 'Asunto de Notificación' },
    { key: 'assigned_to', label: 'Asignado a' },
  ],
};

// Categorías de variables para el panel lateral del editor
const VARIABLE_CATEGORIES = [
  {
    cat: 'Cliente',
    icon: 'Building2',
    iconColor: 'text-blue-500',
    vars: [
      { key: 'Nombre_Cliente', label: 'Razón social del cliente' },
      { key: 'Rif_Cliente', label: 'RIF del cliente' },
      { key: 'Contacto_Principal', label: 'Nombre del contacto' },
      { key: 'Datos_Contacto', label: 'Contacto + Tel + Email' },
      { key: 'Telefono_Contacto', label: 'Teléfono del contacto' },
      { key: 'Email_Contacto', label: 'Correo del contacto' },
      { key: 'client_name', label: 'Nombre del cliente (alias)' },
      { key: 'client_rif', label: 'RIF del cliente (alias)' },
      { key: 'client_address', label: 'Dirección del cliente' },
    ],
  },
  {
    cat: 'Financiero (Ventas)',
    icon: 'CreditCard',
    iconColor: 'text-violet-500',
    vars: [
      { key: 'Cotizacion_Nro', label: 'Número de cotización' },
      { key: 'quote_number', label: 'Número de cotización (alias)' },
      { key: 'nro_cotizacion', label: 'Nro. cotización (reparación)' },
      { key: 'quote_type', label: 'Tipo de cotización' },
      { key: 'total_usd', label: 'Total en USD' },
      { key: 'Monto_Total', label: 'Monto total USD (equipos)' },
      { key: 'invoice_number', label: 'Número de factura' },
      { key: 'Referencia_Factura', label: 'Referencia de factura (equipos)' },
      { key: 'sede_name', label: 'Sede (PYME / CORP)' },
      { key: 'company_name', label: 'Nombre de la empresa' },
      { key: 'items_table', label: 'Tabla HTML de productos' },
      { key: 'services_table', label: 'Tabla de servicios' },
      { key: 'Direccion_Entrega', label: 'Dirección de entrega' },
    ],
  },
  {
    cat: 'Ejecutivo',
    icon: 'Users',
    iconColor: 'text-emerald-500',
    vars: [
      { key: 'Nombre_Ejecutivo', label: 'Nombre del ejecutivo' },
      { key: 'Email_Ejecutivo', label: 'Correo del ejecutivo' },
      { key: 'contacto_cliente', label: 'Contacto del cliente' },
    ],
  },
  {
    cat: 'Implementación (Técnico)',
    icon: 'Server',
    iconColor: 'text-amber-500',
    vars: [
      { key: 'Servidor_Instalacion', label: 'Servidor asignado' },
      { key: 'Lista_VTID', label: 'Lista de VTIDs' },
      { key: 'Modelo_Seriales_POS', label: 'Tabla de POS/Pinpad' },
      { key: 'Modelo_Seriales_Equipos', label: 'Tabla de equipos' },
      { key: 'Nombre_Implementador', label: 'Implementador asignado' },
      { key: 'Correo_Implementador', label: 'Correo del implementador' },
      { key: 'Telefono_Implementador', label: 'Teléfono del implementador' },
      { key: 'Integrador', label: 'Nombre del integrador' },
      { key: 'Aplicativo_Integracion', label: 'App de integración' },
      { key: 'Nombre_Sucursal', label: 'Sucursal(es)' },
      { key: 'Cantidad_Cajas', label: 'Cantidad de cajas' },
      { key: 'Matriz_Bancos_Productos', label: 'Tabla de bancos y productos' },
      { key: 'project_number', label: 'Nro. de proyecto' },
      { key: 'ticket_number', label: 'Nro. de ticket' },
      { key: 'integrator_name', label: 'Integrador (alias)' },
      { key: 'pinpad_model', label: 'Modelo de pinpad' },
    ],
  },
];

// Mapa de iconos para renderización
const ICON_MAP = { Building2, CreditCard, Users, Server };

// Función para obtener variables de una plantilla específica
const getTemplateVariables = (templateId) => {
  if (!templateId) return [];
  // Extraer el tipo base del template_id (ej: quote_sent_TBP -> quote_sent)
  const baseType = templateId.replace(/_PYME$|_CORP$/, '');
  const baseVars = BASE_TEMPLATE_VARIABLES[baseType] || [];
  // Variables comunes disponibles en TODAS las plantillas de cotización/proyecto
  const SHARED_VARS = [
    { key: 'abreviaturas_medios_pago', label: 'Medios de Pago (abreviaturas, separados por /)' },
  ];
  return [...baseVars, ...SHARED_VARS];
};

export const EmailTemplatesEditor = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [saving, setSaving] = useState(false);

  // Crear nueva plantilla personalizada
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    template_id: '',
    name: '',
    context: 'COTIZACIONES',
    group: 'General',
    description: '',
    subject: '',
    body_html: '',
  });
  
  // Formulario de edición
  const [formData, setFormData] = useState({
    subject: '',
    body_html: ''
  });

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const response = await api.get('/email-templates');
      setTemplates(response.data);
    } catch (error) {
      console.error('Error fetching templates:', error);
      toast.error('Error al cargar plantillas');
    } finally {
      setLoading(false);
    }
  };

  const openEditDialog = (template) => {
    setEditingTemplate(template);
    setFormData({
      subject: template.subject || '',
      body_html: template.body_html || ''
    });
    setEditDialogOpen(true);
  };

  const handleSave = async () => {
    if (!editingTemplate) return;
    
    setSaving(true);
    try {
      await api.put(`/email-templates/${editingTemplate.template_id}`, {
        ...editingTemplate,
        subject: formData.subject,
        body_html: formData.body_html
      });
      
      toast.success('Plantilla guardada exitosamente');
      setEditDialogOpen(false);
      fetchTemplates();
    } catch (error) {
      console.error('Error saving template:', error);
      toast.error('Error al guardar plantilla');
    } finally {
      setSaving(false);
    }
  };

  // Generar template_id sugerido a partir del name (slug)
  const slugify = (name) => (name || '')
    .toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 60);

  const openCreateDialog = () => {
    setCreateForm({
      template_id: '',
      name: '',
      context: 'COTIZACIONES',
      group: 'General',
      description: '',
      subject: '',
      body_html: '',
    });
    setCreateDialogOpen(true);
  };

  const handleCreate = async () => {
    let tid = (createForm.template_id || slugify(createForm.name)).trim();
    if (!tid) { toast.error('Debes indicar el ID o el nombre de la plantilla'); return; }
    if (!createForm.name?.trim()) { toast.error('El nombre es obligatorio'); return; }
    if (!createForm.subject?.trim()) { toast.error('El asunto es obligatorio'); return; }
    if (!createForm.body_html?.trim()) { toast.error('El cuerpo HTML es obligatorio'); return; }
    if (!/^[a-z0-9_]+$/i.test(tid)) {
      toast.error('El ID solo puede contener letras, números y guiones bajos'); return;
    }
    // Auto-sufijar template_id según grupo (compatibilidad con legacy)
    const group = createForm.group || 'General';
    if (group === 'Pyme' && !tid.endsWith('_PYME')) tid = `${tid}_PYME`;
    else if (group === 'Corp' && !tid.endsWith('_CORP')) tid = `${tid}_CORP`;

    const payload = {
      template_id: tid,
      name: createForm.name.trim(),
      subject: createForm.subject,
      body_html: createForm.body_html,
      description: createForm.description || '',
      context: createForm.context || null,
      is_active: true,
      group,
      sede: group === 'Pyme' ? 'PYME' : group === 'Corp' ? 'CORP' : null,
      is_project_template: group === 'Implementación',
    };
    setCreating(true);
    try {
      await api.post('/email-templates', payload);
      toast.success(`Plantilla creada en grupo "${group}"`);
      setCreateDialogOpen(false);
      fetchTemplates();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Error al crear plantilla: ${detail}`);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteTemplate = async (templateId) => {
    if (!window.confirm(`¿Eliminar la plantilla "${templateId}"? Esta acción no se puede deshacer.`)) return;
    try {
      await api.delete(`/email-templates/${templateId}`);
      toast.success('Plantilla eliminada');
      fetchTemplates();
    } catch (error) {
      const detail = error.response?.data?.detail || error.message;
      toast.error(`Error al eliminar: ${detail}`);
    }
  };

  const handleReset = async (templateId) => {
    if (!window.confirm('¿Está seguro de restablecer esta plantilla a los valores predeterminados?')) return;    
    try {
      await api.post(`/email-templates/reset/${templateId}`);
      toast.success('Plantilla restablecida');
      fetchTemplates();
      if (editDialogOpen && editingTemplate?.template_id === templateId) {
        // Recargar datos en el formulario
        const response = await api.get(`/email-templates/${templateId}`);
        setFormData({
          subject: response.data.subject,
          body_html: response.data.body_html
        });
      }
    } catch (error) {
      console.error('Error resetting template:', error);
      toast.error('Error al restablecer plantilla');
    }
  };

  const openPreview = () => {
    // Reemplazar variables con ejemplos
    let html = formData.body_html;
    const variables = getTemplateVariables(editingTemplate?.template_id) || [];
    
    const exampleValues = {
      quote_number: 'COT-2024-001',
      client_name: 'Empresa Ejemplo C.A.',
      client_rif: 'J-12345678-9',
      quote_type: 'VPOS',
      total_usd: '1,500.00',
      company_name: 'Gestor WFPI',
      invoice_number: 'FAC-001234',
      client_address: 'Av. Principal, Edificio Centro, Piso 3',
      integrator_name: 'Integrador Demo (App Demo)',
      pinpad_model: 'Verifone P400',
      approved_date: '24/02/2026',
      sede_name: 'Torre Banco Plaza',
      Nombre_Ejecutivo: 'Rafael González',
      Email_Ejecutivo: 'rgonzalez@megasoft.com.ve',
      // Variables de Proyecto
      Nombre_Cliente: 'MegaFarma, C.A.',
      Contacto_Principal: 'Pedro Pérez',
      Nombre_Sucursal: 'Norte, Sur, Este',
      Cantidad_Cajas: 'Norte: 5 | Sur: 2 | Este: 3 (Total: 10)',
      Integrador: 'A2 Softway C.A.',
      Aplicativo_Integracion: 'A2 Softway POS',
      Nombre_Implementador: 'Carlos Rodríguez',
      Correo_Implementador: 'crodriguez@meganexus.com',
      Telefono_Implementador: '+58 412 555-0123',
      Matriz_Bancos_Productos: '<table style="border-collapse:collapse;width:100%;font-size:13px;"><thead><tr style="background:#2c3e50;color:white;"><th style="padding:8px;border:1px solid #ddd;">Banco</th><th style="padding:8px;border:1px solid #ddd;">Producto / Servicio</th><th style="padding:8px;border:1px solid #ddd;text-align:center;">Cantidad</th></tr></thead><tbody><tr><td style="padding:8px;border:1px solid #ddd;">Banco Mercantil</td><td style="padding:8px;border:1px solid #ddd;">Tarjeta de Crédito/Débito</td><td style="padding:8px;border:1px solid #ddd;text-align:center;">1</td></tr><tr style="background:#f8f9fa;"><td style="padding:8px;border:1px solid #ddd;">Banesco</td><td style="padding:8px;border:1px solid #ddd;">C2P o Débito Inmediato</td><td style="padding:8px;border:1px solid #ddd;text-align:center;">1</td></tr></tbody></table>',
      project_number: 'PRY-2026-03-001-PRI',
      ticket_number: '56785',
      bank_name: 'Banco Mercantil',
      bank_products: 'Tarjeta de Crédito/Débito, C2P o Débito Inmediato',
      notification_level: 'Primera Comunicación',
      notification_subject: 'Notificación de Implementación',
      assigned_to: 'Carlos Rodríguez',
      items_table: '<table style="border-collapse:collapse;width:100%"><tr style="background:#f3f4f6"><th style="padding:8px;border:1px solid #ddd">Producto</th><th style="padding:8px;border:1px solid #ddd">Cantidad</th></tr><tr><td style="padding:8px;border:1px solid #ddd">Terminal POS</td><td style="padding:8px;border:1px solid #ddd;text-align:center">2</td></tr></table>',
      services_table: '<table style="border-collapse:collapse;width:100%"><tr style="background:#f3f4f6"><th style="padding:8px;border:1px solid #ddd">Servicio</th><th style="padding:8px;border:1px solid #ddd">Categoría</th></tr><tr><td style="padding:8px;border:1px solid #ddd">Setup Inicial</td><td style="padding:8px;border:1px solid #ddd;text-align:center">setup</td></tr></table>',
      nro_cotizacion: 'COT-2024-001',
      nombre_cliente: 'Empresa Ejemplo C.A.',
      contacto_cliente: 'Juan Pérez',
      modelos_resumen: 'Verifone P400 (x3), Verifone V240m (x2)',
      lista_modelos_seriales: '<p><strong>Verifone P400</strong>: SN001, SN002, SN003</p><p><strong>Verifone V240m</strong>: SN004, SN005</p>',
      tipo_nota_entrega: 'Entrega Final',
      nro_nota_entrega: 'NE-2026-0015',
      cantidad_entregada: '5',
      estatus_entrega: 'Finalizado',
      lista_equipos_seriales: '<p><strong>Verifone P400</strong> (3 uds): SN001, SN002, SN003</p><p><strong>Verifone V240m</strong> (2 uds): SN004, SN005</p>',
      almacen_custodia: 'Torre Banco Plaza',
      // Variables de Equipos
      Monto_Total: '3,500.00',
      Monto_Pagado: '3,500.00',
      Referencia_Factura: 'FAC-EQ-2026-001',
      Direccion_Entrega: 'Av. Libertador, Centro Comercial, Local 5, Caracas',
      Modelo_Equipo: 'Verifone P400',
      Cantidad: '5',
      Banco_Destino: 'Banco Mercantil'
    };
    
    for (const v of variables) {
      const placeholder = `{${v.key}}`;
      html = html.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), exampleValues[v.key] || v.label);
    }
    
    setPreviewHtml(html);
    setPreviewDialogOpen(true);
  };

  const insertVariable = (variable, targetField = 'body') => {
    const elementId = targetField === 'subject' ? 'template-subject' : 'template-body';
    const fieldKey = targetField === 'subject' ? 'subject' : 'body_html';
    const el = document.getElementById(elementId);
    if (el) {
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const text = formData[fieldKey];
      const before = text.substring(0, start);
      const after = text.substring(end);
      const newText = before + `{${variable}}` + after;
      setFormData(prev => ({ ...prev, [fieldKey]: newText }));
      // Restore cursor position after insert
      setTimeout(() => {
        el.focus();
        const newPos = start + variable.length + 2;
        el.setSelectionRange(newPos, newPos);
      }, 50);
    } else {
      setFormData(prev => ({ ...prev, [fieldKey]: prev[fieldKey] + `{${variable}}` }));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin h-8 w-8 border-4 border-brand-blue-600 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  // Agrupar plantillas por sede
  const templatesBySede = {};
  SEDES.forEach(sede => {
    templatesBySede[sede.id] = templates.filter(t => t.template_id?.endsWith(`_${sede.id}`));
  });
  
  // Plantillas legacy (sin sede, no proyecto, no personalizadas)
  const legacyTemplates = templates.filter(t => !t.template_id?.endsWith('_PYME') && !t.template_id?.endsWith('_CORP') && !t.is_project_template && !t.is_custom && !PROJECT_TEMPLATE_TYPES.some(pt => pt.templateId === t.template_id));

  // Plantillas de proyecto (globales)
  const projectTemplates = templates.filter(t => t.is_project_template || PROJECT_TEMPLATE_TYPES.some(pt => pt.templateId === t.template_id));

  // Plantillas personalizadas (creadas por el usuario admin)
  const customTemplates = templates.filter(t => t.is_custom === true);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-2 text-slate-600">
          <AlertCircle size={16} />
          <span className="text-sm">Use <code className="bg-slate-100 px-1 rounded">{'{variable}'}</code> para insertar datos dinámicos en las plantillas.</span>
        </div>
        <Button
          onClick={openCreateDialog}
          className="bg-violet-600 hover:bg-violet-700 text-white"
          data-testid="create-template-btn"
        >
          <Plus size={16} className="mr-2" />
          Crear Nueva Plantilla
        </Button>
      </div>

      {/* ===== Sección: Plantillas Personalizadas ===== */}
      {customTemplates.length > 0 && (
        <div className="border border-violet-200 rounded-lg overflow-hidden">
          <div className="bg-gradient-to-r from-violet-50 to-fuchsia-50 px-4 py-3 border-b border-violet-200">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-violet-600" />
              <span className="font-semibold text-slate-800">Plantillas Personalizadas</span>
              <span className="text-xs text-violet-700 bg-violet-100 px-2 py-0.5 rounded-full">{customTemplates.length}</span>
            </div>
            <p className="text-xs text-slate-600 mt-1">
              Plantillas creadas manualmente. Disponibles en el Motor Dinámico de Notificaciones para asignar a cualquier acción del flujo.
            </p>
          </div>
          <div className="p-4 space-y-3">
            {customTemplates.map((template) => (
              <div
                key={template.template_id}
                className="p-3 rounded-lg border border-violet-200 bg-white"
                data-testid={`email-template-${template.template_id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="p-2 rounded-lg bg-violet-50 text-violet-600 flex-shrink-0">
                      <Sparkles size={18} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-medium text-slate-900 text-sm truncate">{template.name}</h3>
                        <code className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">{template.template_id}</code>
                        {template.context && (
                          <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{template.context}</span>
                        )}
                      </div>
                      {template.description && <p className="text-xs text-slate-600 mt-0.5">{template.description}</p>}
                      <div className="mt-1 text-xs text-slate-500 truncate">
                        <span className="font-medium">Asunto:</span> {template.subject}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEditDialog(template)}
                      className="h-7 text-xs"
                      data-testid={`edit-template-${template.template_id}`}
                    >
                      <Edit size={12} className="mr-1" />
                      Editar
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteTemplate(template.template_id)}
                      className="h-7 text-red-500 hover:text-red-700 hover:bg-red-50"
                      title="Eliminar plantilla"
                      data-testid={`delete-template-${template.template_id}`}
                    >
                      <Trash2 size={12} />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plantillas agrupadas por sede */}
      {SEDES.map((sede) => (
        <div key={sede.id} className="border border-slate-200 rounded-lg overflow-hidden">
          {/* Header de la Sede */}
          <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
            <div className="flex items-center gap-2">
              <MapPin size={18} className="text-slate-600" />
              <span className="font-semibold text-slate-800">Plantillas Sede {sede.name}</span>
            </div>
          </div>
          
          <div className="p-4 space-y-3">
            {templatesBySede[sede.id]?.length > 0 ? (
              templatesBySede[sede.id].map((template) => {
                const config = TEMPLATE_CONFIG[template.template_id] || {};
                const IconComponent = config.icon || Mail;
                
                return (
                  <div 
                    key={template.template_id}
                    className={`p-3 rounded-lg border ${config.borderColor || 'border-slate-200'} ${config.bgColor || 'bg-slate-50'}`}
                    data-testid={`email-template-${template.template_id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className={`p-2 rounded-lg bg-white ${config.color || 'text-slate-600'}`}>
                          <IconComponent size={20} />
                        </div>
                        <div>
                          <h3 className="font-medium text-slate-900 text-sm">{config.title || template.name}</h3>
                          <p className="text-xs text-slate-600 mt-0.5">{config.description || template.description}</p>
                          <div className="mt-1 text-xs text-slate-500">
                            <span className="font-medium">Asunto:</span> {template.subject?.substring(0, 40)}...
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openEditDialog(template)}
                          className="h-7 text-xs"
                          data-testid={`edit-template-${template.template_id}`}
                        >
                          <Edit size={12} className="mr-1" />
                          Editar
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleReset(template.template_id)}
                          className="h-7 text-slate-500 hover:text-red-600"
                          data-testid={`reset-template-${template.template_id}`}
                        >
                          <RotateCcw size={12} />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="text-sm text-slate-500 text-center py-4">
                No hay plantillas configuradas para esta sede. Se crearán automáticamente.
              </p>
            )}
          </div>
        </div>
      ))}

      {/* ===== Sección: Plantillas de Proyecto (Implementación) ===== */}
      {projectTemplates.length > 0 && (
        <div className="border border-orange-200 rounded-lg overflow-hidden">
          <div className="bg-gradient-to-r from-orange-50 to-teal-50 px-4 py-3 border-b border-orange-200">
            <div className="flex items-center gap-2">
              <Settings2 size={18} className="text-orange-600" />
              <span className="font-semibold text-slate-800">Plantillas de Proyecto (Implementación)</span>
            </div>
            <p className="text-xs text-slate-600 mt-1">
              Plantillas para las comunicaciones secuenciales con clientes y bancos durante el proceso de implementación.
              Las variables se resuelven automáticamente desde los datos del proyecto.
            </p>
          </div>
          
          <div className="p-4 space-y-3">
            {projectTemplates.map((template) => {
              const ptConfig = PROJECT_TEMPLATE_TYPES.find(pt => pt.templateId === template.template_id) || {};
              const IconComponent = ptConfig.icon || Mail;
              
              return (
                <div 
                  key={template.template_id}
                  className={`p-3 rounded-lg border ${ptConfig.borderColor || 'border-slate-200'} ${ptConfig.bgColor || 'bg-slate-50'}`}
                  data-testid={`email-template-${template.template_id}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg bg-white ${ptConfig.color || 'text-slate-600'}`}>
                        <IconComponent size={20} />
                      </div>
                      <div>
                        <h3 className="font-medium text-slate-900 text-sm">{ptConfig.title || template.name}</h3>
                        <p className="text-xs text-slate-600 mt-0.5">{ptConfig.description || template.description}</p>
                        <div className="mt-1 text-xs text-slate-500">
                          <span className="font-medium">Asunto:</span> {template.subject?.substring(0, 50)}...
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEditDialog(template)}
                        className="h-7 text-xs"
                        data-testid={`edit-template-${template.template_id}`}
                      >
                        <Edit size={12} className="mr-1" />
                        Editar
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleReset(template.template_id)}
                        className="h-7 text-slate-500 hover:text-red-600"
                      >
                        <RotateCcw size={12} />
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Plantillas legacy (sin sede) - mostrar si existen */}
      {legacyTemplates.length > 0 && (
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <div className="bg-amber-50 px-4 py-3 border-b border-amber-200">
            <div className="flex items-center gap-2">
              <AlertCircle size={18} className="text-amber-600" />
              <span className="font-semibold text-amber-800">Plantillas Generales (Sin Sede)</span>
            </div>
            <p className="text-xs text-amber-700 mt-1">Estas plantillas se migrarán a plantillas por sede.</p>
          </div>
          
          <div className="p-4 space-y-3">
            {legacyTemplates.map((template) => {
              const config = TEMPLATE_CONFIG[template.template_id] || {};
              const IconComponent = config.icon || Mail;
              
              return (
                <div 
                  key={template.template_id}
                  className={`p-3 rounded-lg border ${config.borderColor || 'border-slate-200'} ${config.bgColor || 'bg-slate-50'}`}
                  data-testid={`email-template-${template.template_id}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg bg-white ${config.color || 'text-slate-600'}`}>
                        <IconComponent size={20} />
                      </div>
                      <div>
                        <h3 className="font-medium text-slate-900 text-sm">{config.title || template.name}</h3>
                        <p className="text-xs text-slate-600 mt-0.5">{config.description || template.description}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEditDialog(template)}
                        className="h-7 text-xs"
                      >
                        <Edit size={12} className="mr-1" />
                        Editar
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Dialog de edición — Layout con sidebar de variables */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto" data-testid="master-template-edit-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit className="text-brand-blue-600" size={20} />
              Editar Plantilla: {TEMPLATE_CONFIG[editingTemplate?.template_id]?.title || editingTemplate?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="grid grid-cols-3 gap-6 py-4">
            {/* Col 1-2: Editor */}
            <div className="col-span-2 space-y-4">
              {/* Asunto */}
              <div>
                <Label htmlFor="template-subject" className="font-semibold">
                  Asunto del Correo
                </Label>
                <Input
                  id="template-subject"
                  value={formData.subject}
                  onChange={(e) => setFormData(prev => ({ ...prev, subject: e.target.value }))}
                  placeholder="Asunto del correo..."
                  className="mt-1"
                  data-testid="template-subject-input"
                />
              </div>

              {/* Cuerpo del correo */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <Label htmlFor="template-body" className="font-semibold">
                    Cuerpo del Correo (HTML)
                  </Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={openPreview}
                    className="text-brand-blue-600"
                  >
                    <Eye size={14} className="mr-1" />
                    Vista Previa
                  </Button>
                </div>
                <Textarea
                  id="template-body"
                  value={formData.body_html}
                  onChange={(e) => setFormData(prev => ({ ...prev, body_html: e.target.value }))}
                  placeholder="Contenido HTML del correo..."
                  rows={18}
                  className="font-mono text-sm"
                  data-testid="template-body-input"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Use HTML para dar formato. Las variables entre llaves se reemplazan automáticamente.
                </p>
              </div>

              {/* Acciones */}
              <div className="flex justify-between items-center pt-2 border-t border-slate-200">
                <Button
                  variant="ghost"
                  onClick={() => handleReset(editingTemplate?.template_id)}
                  className="text-slate-500"
                >
                  <RotateCcw size={14} className="mr-1" />
                  Restablecer
                </Button>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-brand-green-600 hover:bg-brand-green-700"
                    data-testid="save-template-btn"
                  >
                    <Save size={14} className="mr-1" />
                    {saving ? 'Guardando...' : 'Guardar Plantilla'}
                  </Button>
                </div>
              </div>
            </div>

            {/* Col 3: Panel Diccionario de Variables (Sidebar) */}
            <div className="col-span-1 border-l border-slate-200 pl-4" data-testid="master-variables-sidebar">
              <p className="text-xs font-semibold text-slate-600 uppercase mb-1">Panel de Variables</p>
              <p className="text-[10px] text-slate-400 mb-3">Clic en una variable para copiarla e insertarla en el cuerpo.</p>
              <div className="space-y-4 max-h-[55vh] overflow-y-auto pr-1">
                {VARIABLE_CATEGORIES.map(group => {
                  const IconComp = ICON_MAP[group.icon] || FileText;
                  return (
                    <div key={group.cat}>
                      <div className="flex items-center gap-1.5 mb-2">
                        <IconComp size={14} className={group.iconColor} />
                        <span className="text-xs font-bold text-slate-700">{group.cat}</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5 mb-1">
                        {group.vars.map(v => (
                          <button
                            key={v.key}
                            title={v.label}
                            data-testid={`master-var-${v.key}`}
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-mono rounded-md cursor-pointer transition-all
                              bg-[#EBF8FF] text-[#2C5282] border border-[#BEE3F8]
                              hover:bg-[#BEE3F8] hover:border-[#90CDF4] hover:text-[#2A4365]"
                            onClick={() => {
                              const tag = `{${v.key}}`;
                              try { navigator.clipboard.writeText(tag).then(() => toast.success(`Copiado: ${tag}`)); } catch(e) { /* fallback */ }
                              insertVariable(v.key, 'body');
                            }}
                          >
                            <span>{`{${v.key}}`}</span>
                            <Copy size={10} className="opacity-40" />
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Variables específicas de la plantilla actual */}
              {getTemplateVariables(editingTemplate?.template_id).length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-200">
                  <p className="text-[10px] font-semibold text-slate-500 uppercase mb-2">Variables de esta plantilla</p>
                  <div className="flex flex-wrap gap-1">
                    {getTemplateVariables(editingTemplate?.template_id).map(v => (
                      <button
                        key={`spec-${v.key}`}
                        title={v.label}
                        data-testid={`spec-var-${v.key}`}
                        className="px-1.5 py-0.5 text-[10px] font-mono rounded
                          bg-[#EBF8FF] text-[#2C5282] border border-[#BEE3F8]
                          hover:bg-[#BEE3F8] hover:border-[#90CDF4] cursor-pointer transition-all"
                        onClick={() => insertVariable(v.key, 'body')}
                      >
                        {`{${v.key}}`}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Dialog de vista previa */}
      <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Eye className="text-brand-blue-600" size={20} />
              Vista Previa del Correo
            </DialogTitle>
          </DialogHeader>

          <div className="border rounded-lg p-4 bg-white max-h-[60vh] overflow-y-auto">
            <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>
              <X size={14} className="mr-1" />
              Cerrar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog: Crear nueva plantilla personalizada */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="create-template-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles size={20} className="text-violet-600" />
              Crear Nueva Plantilla
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Nombre *</Label>
                <Input
                  value={createForm.name}
                  onChange={(e) => {
                    const name = e.target.value;
                    setCreateForm((f) => ({
                      ...f,
                      name,
                      // Auto-generar ID si el usuario aún no escribió uno manual
                      template_id: f.template_id ? f.template_id : slugify(name),
                    }));
                  }}
                  placeholder="Ej: Bienvenida cliente nuevo"
                  data-testid="create-template-name"
                />
              </div>
              <div>
                <Label className="text-xs">ID técnico * (a-z, 0-9, _)</Label>
                <Input
                  value={createForm.template_id}
                  onChange={(e) => setCreateForm((f) => ({ ...f, template_id: e.target.value }))}
                  placeholder="bienvenida_cliente_nuevo"
                  className="font-mono text-sm"
                  data-testid="create-template-id"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Grupo *</Label>
                <Select value={createForm.group || 'General'} onValueChange={(v) => setCreateForm((f) => ({ ...f, group: v }))}>
                  <SelectTrigger data-testid="create-template-group"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Pyme">Pyme (sufijo _PYME)</SelectItem>
                    <SelectItem value="Corp">Corp (sufijo _CORP)</SelectItem>
                    <SelectItem value="Implementación">Implementación</SelectItem>
                    <SelectItem value="General">General</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Contexto</Label>
                <Select value={createForm.context || 'COTIZACIONES'} onValueChange={(v) => setCreateForm((f) => ({ ...f, context: v }))}>
                  <SelectTrigger data-testid="create-template-context"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="COTIZACIONES">Cotizaciones</SelectItem>
                    <SelectItem value="IMPLEMENTACION">Implementación</SelectItem>
                    <SelectItem value="ADMINISTRACION">Administración</SelectItem>
                    <SelectItem value="CLIENTES">Clientes</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Descripción (opcional)</Label>
                <Input
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Cuándo se usa esta plantilla"
                  data-testid="create-template-description"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">Asunto *</Label>
              <Input
                value={createForm.subject}
                onChange={(e) => setCreateForm((f) => ({ ...f, subject: e.target.value }))}
                placeholder="Asunto del correo (puedes usar {variable})"
                data-testid="create-template-subject"
              />
            </div>
            <div>
              <Label className="text-xs">Cuerpo HTML *</Label>
              <Textarea
                value={createForm.body_html}
                onChange={(e) => setCreateForm((f) => ({ ...f, body_html: e.target.value }))}
                placeholder="<html><body><p>Hola {client_name},</p>...</body></html>"
                rows={12}
                className="font-mono text-xs"
                data-testid="create-template-body"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Escribe HTML directo. Usa <code className="bg-slate-100 px-1 rounded">{'{variable}'}</code> para datos dinámicos
                (por ej. <code className="bg-slate-100 px-1 rounded">{'{client_name}'}</code>, <code className="bg-slate-100 px-1 rounded">{'{quote_number}'}</code>).
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)} disabled={creating} data-testid="create-template-cancel">
              Cancelar
            </Button>
            <Button onClick={handleCreate} disabled={creating} className="bg-violet-600 hover:bg-violet-700" data-testid="create-template-confirm">
              {creating ? 'Creando...' : (<><Save size={14} className="mr-2" />Crear Plantilla</>)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EmailTemplatesEditor;
