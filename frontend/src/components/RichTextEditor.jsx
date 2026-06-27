import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import { Extension } from '@tiptap/core';
import { Plugin } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { TableKit } from '@tiptap/extension-table';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import Highlight from '@tiptap/extension-highlight';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import { toast } from 'sonner';
import api from '../utils/api';
import {
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  List, ListOrdered, AlignLeft, AlignCenter, AlignRight, AlignJustify,
  Palette, Highlighter, Link as LinkIcon, Eye, X, Undo2, Redo2,
  Rows3, Trash2, ImagePlus,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';

/**
 * Extensión ProseMirror: botón de papelera por fila para borrado "fricción cero"
 * de la {Matriz_Bancos_Productos} dentro del editor de la notificación.
 *
 * Implementado con widget decorations: el botón NO forma parte del documento, por
 * lo que NUNCA se serializa en getHTML() (no viaja en el correo). El borrado es
 * estrictamente local/efímero (solo afecta al cuerpo en preparación; jamás la BD).
 * Las filas de encabezado (<th>) se excluyen.
 */
const TRASH_ICON_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';

// Identifica la tabla de la Matriz de Bancos/Productos por su encabezado.
const MATRIX_HEADER_RE = /Producto\s*\/\s*Servicio/i;

function _buildRowDeleteButton() {
  // Botón visual únicamente. La lógica de borrado se maneja por DELEGACIÓN de
  // eventos en el plugin (handleDOMEvents), porque ProseMirror recrea el DOM del
  // widget en cada actualización de decoraciones y descartaría un addEventListener.
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'rte-row-del';
  btn.contentEditable = 'false';
  btn.setAttribute('data-testid', 'matrix-row-delete');
  btn.setAttribute('title', 'Eliminar fila');
  btn.innerHTML = TRASH_ICON_SVG;
  return btn;
}

function _resolveRowRange(view, btn) {
  // Resuelve el rango PM de la fila de forma SÍNCRONA (DOM aún conectado), usando
  // la última celda (sin widget; la primera celda contiene el botón y posAtDOM ahí
  // devuelve -1). Debe llamarse ANTES de que PM recomponga las decoraciones.
  const trEl = btn.closest('tr');
  if (!trEl) return null;
  const cellEl = trEl.querySelector('td:last-child') || trEl.querySelector('td, th');
  if (!cellEl) return null;
  const pos = view.posAtDOM(cellEl, 0);
  if (pos < 0) return null;
  const $pos = view.state.doc.resolve(pos);
  let depth = $pos.depth;
  while (depth > 0 && $pos.node(depth).type.name !== 'tableRow') depth--;
  if (depth <= 0) return null;
  return { trEl, from: $pos.before(depth), to: $pos.after(depth) };
}

const TableRowActions = Extension.create({
  name: 'tableRowActions',
  addProseMirrorPlugins() {
    return [
      new Plugin({
        props: {
          handleDOMEvents: {
            mousedown(view, event) {
              const target = event.target;
              const btn = target && target.closest && target.closest('[data-testid="matrix-row-delete"]');
              if (!btn) return false;
              event.preventDefault();
              event.stopPropagation();
              // 1) Resolver el rango de la fila YA (antes de cualquier recomposición).
              let range;
              try {
                range = _resolveRowRange(view, btn);
              } catch (err) {
                console.warn('[matrix] resolve row failed', err);
                return true;
              }
              if (!range) return true;
              // 2) Transición suave sobre la fila viva.
              if (range.trEl) range.trEl.classList.add('rte-row-removing');
              // 3) Borrar usando posiciones capturadas (la selección no altera el doc).
              window.setTimeout(() => {
                try {
                  view.dispatch(view.state.tr.delete(range.from, range.to));
                } catch (err) {
                  console.warn('[matrix] row delete failed', err);
                }
              }, 160);
              return true;
            },
          },
          decorations(state) {
            // Solo decorar las filas de la Matriz de Bancos/Productos (no las tablas
            // de Datos del Cliente/Banco/Implementación) para evitar borrados accidentales.
            const matrixRanges = [];
            state.doc.descendants((node, pos) => {
              if (node.type.name === 'table' && MATRIX_HEADER_RE.test(node.textContent || '')) {
                matrixRanges.push([pos, pos + node.nodeSize]);
              }
            });
            if (matrixRanges.length === 0) return DecorationSet.empty;

            const decos = [];
            state.doc.descendants((node, pos) => {
              if (node.type.name !== 'tableRow') return;
              if (!matrixRanges.some(([s, e]) => pos >= s && pos < e)) return;
              // Excluir filas de encabezado (no se pueden eliminar)
              const first = node.firstChild;
              if (first && first.type.name === 'tableHeader') return;

              decos.push(Decoration.node(pos, pos + node.nodeSize, { class: 'rte-row-actionable' }));
              decos.push(
                Decoration.widget(pos + 1, () => _buildRowDeleteButton(), {
                  side: -1,
                  ignoreSelection: true,
                }),
              );
            });
            return DecorationSet.create(state.doc, decos);
          },
        },
      }),
    ];
  },
});

/**
 * Mapa por defecto de tokens → valores de ejemplo para Vista Previa.
 * El padre puede extenderlo vía la prop `exampleValues`.
 */
const DEFAULT_EXAMPLE_VALUES = {
  nombre: 'CLIENTE DEMO S.A.',
  rif: 'J-12345678-9',
  email: 'contacto@clientedemo.com',
  contacto: 'María Pérez',
  direccion: 'Av. Principal, Edificio Centro, Piso 3',
  telefono: '+58 212 555-0100',
  nombre_comercial: 'Cliente Demo',
  nombre_integrador: 'Integrador Demo',
  razon_social: 'Integrador Demo, C.A.',
  estado: 'Homologado',
  aplicativo: 'Demo App POS',
  fase: 'Producción',
  producto: 'Producto Demo',
  categoria: 'Software',
  desarrollador: 'Equipo I+D',
  sqa: 'Equipo QA',
  fecha_entrega: '31/03/2026',
  banco: 'Banco Mercantil',
  client_name: 'CLIENTE DEMO S.A.',
  client_rif: 'J-12345678-9',
  client_address: 'Av. Principal, Edificio Centro, Piso 3',
  quote_number: 'COT-2026-001',
  quote_type: 'VPOS',
  total_usd: '1,500.00',
  invoice_number: 'FAC-001234',
  company_name: 'Mega Soft Computación, C.A.',
  sede_name: 'PYME',
  approved_date: '24/02/2026',
  Nombre_Cliente: 'CLIENTE DEMO S.A.',
  Rif_Cliente: 'J-12345678-9',
  Contacto_Principal: 'María Pérez',
  Datos_Contacto: 'María Pérez · +58 212 555-0100 · contacto@clientedemo.com',
  Telefono_Contacto: '+58 212 555-0100',
  Email_Contacto: 'contacto@clientedemo.com',
  Cotizacion_Nro: 'COT-2026-001',
  nro_cotizacion: 'COT-2026-001',
  Monto_Total: '1,500.00',
  Referencia_Factura: 'FAC-EQ-2026-001',
  Nombre_Ejecutivo: 'Rafael González',
  Email_Ejecutivo: 'rgonzalez@megasoft.com.ve',
  Nombre_Implementador: 'Carlos Rodríguez',
  Correo_Implementador: 'crodriguez@meganexus.com',
  Telefono_Implementador: '+58 412 555-0123',
  Integrador: 'A2 Softway C.A.',
  Aplicativo_Integracion: 'A2 Softway POS',
  Nombre_Sucursal: 'Sede Norte',
  Cantidad_Cajas: '5',
  Matriz_Bancos_Productos: '<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">Matriz de Bancos y Productos</div><div style="margin:0 0 18px;"><div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">Banco: Banco Mercantil</div><table style="border-collapse:collapse;width:auto;max-width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Producto / Servicio</th><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;width:120px;">Cantidad</th></tr></thead><tbody><tr style="background:#f8fafc;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Tarjeta de Crédito/Débito</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">2</td></tr></tbody></table></div><div style="margin:0 0 18px;"><div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">Banco: Banesco</div><table style="border-collapse:collapse;width:auto;max-width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Producto / Servicio</th><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;width:120px;">Cantidad</th></tr></thead><tbody><tr style="background:#f8fafc;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">C2P o Débito Inmediato</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">1</td></tr></tbody></table></div>',
  Matriz_Sucursales: '<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">Sucursales y Cajas</div><table style="border-collapse:collapse;width:auto;max-width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Sucursal</th><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;width:130px;">Cantidad de Cajas</th></tr></thead><tbody><tr style="background:#f8fafc;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Sede Norte</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">5</td></tr><tr><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Sede Sur</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#334155;font-weight:700;">3</td></tr><tr style="background:#e8eef5;font-weight:700;color:#1f3a5f;"><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;">Total</td><td style="padding:6px 10px;border:1px solid #d8dee9;text-align:center;font-size:11px;">8</td></tr></tbody></table>',
  Matriz_Avance_Proyecto: '<div style="margin:6px 0 10px;padding:8px 12px;border-radius:8px;background:#f0f6ff;border:1px solid #cfe0f5;font-family:Arial,sans-serif;font-size:13px;"><b>Avance Global del Proyecto:</b> <span style="color:#2563eb;font-weight:800;">62%</span></div><table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Banco / Producto</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Recibido</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Configurado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Testeado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">En Producción</th></tr></thead><tbody><tr style="background:#e8eef5;font-weight:700;color:#1f3a5f;"><td colspan="5" style="padding:6px 10px;border:1px solid #d8dee9;font-size:12px;">Banco: Bancamiga</td></tr><tr><td style="padding:6px 10px 6px 22px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Tarjeta de Crédito/Débito</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;">100%</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;">50%</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td></tr></tbody></table>',
  Matriz_Avance_Proyecto_Con_Fecha: '<div style="margin:6px 0 10px;padding:8px 12px;border-radius:8px;background:#f0f6ff;border:1px solid #cfe0f5;font-family:Arial,sans-serif;font-size:13px;"><b>Avance Global del Proyecto:</b> <span style="color:#2563eb;font-weight:800;">62%</span></div><table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:12px;font-weight:700;">Banco / Producto</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Recibido</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Configurado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">Testeado</th><th style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:700;">En Producción</th></tr></thead><tbody><tr style="background:#e8eef5;font-weight:700;color:#1f3a5f;"><td colspan="5" style="padding:6px 10px;border:1px solid #d8dee9;font-size:12px;">Banco: Bancamiga</td></tr><tr><td style="padding:6px 10px 6px 22px;border:1px solid #d8dee9;font-size:11px;color:#334155;">Tarjeta de Crédito/Débito</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;">100%<div style="font-size:10px;color:#64748b;font-weight:400;margin-top:2px;">10/06/2026</div></td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;">50%<div style="font-size:10px;color:#64748b;font-weight:400;margin-top:2px;">11/06/2026</div></td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#9ca3af;font-weight:400;">—</td></tr></tbody></table>',
  Matriz_Seguimiento_Evolutiva: '<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">Matriz de Seguimiento Evolutiva &middot; Todos los bancos <span style="font-weight:400;color:#94a3b8;">&mdash; formato celda: % avance / cajas estimadas / cajas recibidas</span></div><div style="margin:0 0 16px;"><div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">Banco A</div><table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;"><thead><tr style="background:#1f3a5f;color:#fff;"><th rowspan="2" style="padding:7px 10px;border:1px solid #d8dee9;text-align:left;font-size:11px;min-width:170px;vertical-align:middle;">Estructura del Cliente</th><th colspan="4" style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;">Cr&eacute;dito</th><th colspan="4" style="padding:7px 9px;border:1px solid #d8dee9;text-align:center;font-size:12px;font-weight:700;">D&eacute;bito</th></tr><tr style="background:#2c5378;color:#fff;"><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase I</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase II</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase III</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase IV</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase I</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase II</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase III</th><th style="padding:6px 8px;border:1px solid #d8dee9;text-align:center;font-size:11px;font-weight:600;">Fase IV</th></tr></thead><tbody><tr><td colspan="9" style="padding:6px 10px;border:1px solid #d8dee9;background:#e8eef5;color:#1f3a5f;font-weight:700;font-size:12px;">RIF: Comercio XYZ &mdash; RIF: J-00343075-7</td></tr><tr><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;"><span style="color:#94a3b8;">&#9492;&#9472;</span> Sucursal Caracas Centro</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 5 / 5</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;white-space:nowrap;">40% / 5 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 5 / 5</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 5 / 0</td></tr><tr><td style="padding:6px 10px;border:1px solid #d8dee9;font-size:11px;color:#334155;"><span style="color:#94a3b8;">&#9492;&#9472;</span> Sucursal El Hatillo</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 2 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 2 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#16a34a;font-weight:700;white-space:nowrap;">100% / 2 / 2</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#d97706;font-weight:700;white-space:nowrap;">50% / 2 / 1</td><td style="padding:6px 9px;border:1px solid #d8dee9;text-align:center;font-size:11px;color:#64748b;font-weight:700;white-space:nowrap;">0% / 2 / 0</td></tr></tbody></table><div style="font-family:Arial,sans-serif;font-size:10.5px;color:#64748b;margin:4px 0 0;text-align:left;"><strong>Estatus de las Fases:</strong> Fase I = Recibido &nbsp;|&nbsp; Fase II = Configurado &nbsp;|&nbsp; Fase III = Testeado &nbsp;|&nbsp; Fase IV = En Producci&oacute;n</div></div>',
  project_number: 'PRY-2026-03-001-PRI',
  ticket_number: '56785',
  Nro_Proyecto: 'PRY-2026-03-001-PRI',
  Ticket_Nro: '56785',
  Nro_Ticket: '56785',
  Fecha_Asignacion: '24/02/2026',
  Fecha_Desbloqueo_Ticket: '25/02/2026',
  Tipo_Proyecto: 'VPOS',
  bank_name: 'Banco Mercantil',
  notification_level: 'Primera Comunicación',
  notification_subject: 'Notificación de Implementación',
  assigned_to: 'Carlos Rodríguez',
  Direccion_Entrega: 'Av. Libertador, CC Galerías, Local 5',
  Modelo_Equipo: 'Verifone P400',
  Cantidad: '5',
  Banco_Destino: 'Banco Mercantil',
  Patrocinador: 'Banco Mercantil',
};

/** Reemplaza tokens {{var}} y {var} con valores de ejemplo (o [var] si no existe). */
export function substituteTokens(html, extra = {}) {
  const values = { ...DEFAULT_EXAMPLE_VALUES, ...(extra || {}) };
  let out = String(html || '');
  out = out.replace(/\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g, (_, k) => (values[k] !== undefined ? String(values[k]) : `[${k}]`));
  out = out.replace(/\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}/g, (_, k) => (values[k] !== undefined ? String(values[k]) : `[${k}]`));
  return out;
}

/** Devuelve el valor demo asociado a un token (o null si no existe). */
export function getExampleValue(token, extra = {}) {
  const values = { ...DEFAULT_EXAMPLE_VALUES, ...(extra || {}) };
  return values[token] !== undefined ? String(values[token]) : null;
}

const BG_COLORS = ['#FEF3C7', '#FECACA', '#BBF7D0', '#BFDBFE', '#E9D5FF', '#FCE7F3', '#FED7AA'];

/**
 * RichTextEditor — Editor WYSIWYG basado en TipTap.
 * Props:
 *  - value, onChange(html, plainTextLength)
 *  - maxChars (límite de texto visible, default 500)
 *  - hardLimit (default true): si true, revierte ediciones que superan maxChars.
 *      Para plantillas largas pase hardLimit={false} con maxChars alto (ej 20000).
 *  - placeholder, testid
 *  - showPreview (default false): muestra botón Vista Previa con substitución de tokens
 *  - exampleValues: objeto con tokens custom de la pantalla actual
 */
export const RichTextEditor = forwardRef(function RichTextEditor({
  value,
  onChange,
  maxChars = 500,
  hardLimit = true,
  placeholder,
  testid = 'rich-text-editor',
  showPreview = false,
  exampleValues = null,
  minHeight = 110,
  maxHeight = 260,
  tableRowActions = false,
  enableImagePaste = true,
  imageUploadUrl = '/projects/upload-image',
}, ref) {
  const [showHighlights, setShowHighlights] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const editorRef = useRef(null);
  const fileInputRef = useRef(null);

  // Sube un Blob/File de imagen al servidor de archivos y devuelve la URL pública absoluta.
  const uploadImageBlob = async (file) => {
    const mimeExt = (file.type && file.type.split('/')[1]) || 'png';
    const ext = mimeExt === 'jpeg' ? 'jpg' : mimeExt;
    const filename = file.name && file.name.includes('.') ? file.name : `pegado_${Date.now()}.${ext}`;
    const fd = new FormData();
    fd.append('file', file, filename);
    const { data } = await api.post(imageUploadUrl, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
    return data?.url;
  };

  // Procesa una imagen del portapapeles / drop / selector e inserta <img> en el cursor.
  const handleImageFile = async (file) => {
    const ed = editorRef.current;
    if (!ed || !file) return;
    const tId = toast.loading('Subiendo imagen…');
    setUploadingImage(true);
    try {
      const url = await uploadImageBlob(file);
      if (url) {
        ed.chain().focus().setImage({ src: url, alt: file.name || 'imagen' }).run();
        toast.success('Imagen insertada', { id: tId });
      } else {
        toast.error('No se recibió la URL de la imagen', { id: tId });
      }
    } catch (e) {
      toast.error('No se pudo subir la imagen', { id: tId });
    } finally {
      setUploadingImage(false);
    }
  };

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: false, codeBlock: false, blockquote: false, horizontalRule: false, link: false, underline: false }),
      Underline,
      TableKit.configure({ table: { resizable: false, HTMLAttributes: { class: 'rte-table' } } }),
      TextStyle,
      Color,
      Highlight.configure({ multicolor: true }),
      TextAlign.configure({ types: ['paragraph'] }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank', class: 'text-blue-600 underline' },
      }),
      Image.configure({
        inline: false,
        allowBase64: false,
        HTMLAttributes: { style: 'max-width:100%;height:auto;border-radius:6px;display:block;margin:6px 0;' },
      }),
      ...(tableRowActions ? [TableRowActions] : []),
    ],
    content: value || '',
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none focus:outline-none px-3 py-2 text-sm',
        style: `min-height:${minHeight}px;max-height:${maxHeight}px;overflow-y:auto;`,
        'data-testid': `${testid}-content`,
      },
      // Pegado en caliente (Ctrl+V) de imágenes del portapapeles → upload + <img>.
      handlePaste: (view, event) => {
        if (!enableImagePaste) return false;
        const items = event.clipboardData && event.clipboardData.items;
        if (!items) return false;
        for (let i = 0; i < items.length; i++) {
          const it = items[i];
          if (it.kind === 'file' && it.type && it.type.startsWith('image/')) {
            const file = it.getAsFile();
            if (file) {
              event.preventDefault();
              handleImageFile(file);
              return true;
            }
          }
        }
        // Sin bitmap en el portapapeles: detectar imágenes remotas NO incrustables
        // (copiadas desde Gmail/Outlook, requieren sesión) y avisar — esas llegan
        // rotas al destinatario. El backend solo puede incrustar nuestras imágenes,
        // data URIs o imágenes públicas.
        try {
          const pastedHtml = event.clipboardData.getData && event.clipboardData.getData('text/html');
          if (pastedHtml && /<img[^>]+src=["']https?:\/\/(mail\.google\.com|[^"']*googleusercontent\.com|[^"']*\.mail\.[^"']+|outlook\.[^"']+)/i.test(pastedHtml)) {
            toast.warning('Las imágenes copiadas desde un correo no se pueden incrustar y llegarían rotas al cliente. Pega una captura de pantalla (Ctrl+V de la imagen) o súbela con el botón de imagen.', { duration: 8000 });
          }
        } catch (_e) { /* noop */ }
        return false;
      },
      // Soporte de arrastrar-y-soltar imágenes.
      handleDrop: (view, event) => {
        if (!enableImagePaste) return false;
        const files = event.dataTransfer && event.dataTransfer.files;
        if (files && files.length) {
          for (let i = 0; i < files.length; i++) {
            if (files[i].type && files[i].type.startsWith('image/')) {
              event.preventDefault();
              handleImageFile(files[i]);
              return true;
            }
          }
        }
        return false;
      },
    },
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const plainText = editor.getText();
      if (hardLimit && plainText.length > maxChars) {
        editor.commands.undo();
        return;
      }
      onChange && onChange(html, plainText.length);
    },
  });

  useEffect(() => { editorRef.current = editor; }, [editor]);

  useEffect(() => {
    if (editor && value !== undefined && value !== editor.getHTML()) {
      editor.commands.setContent(value || '', false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Forzar re-render de la toolbar al cambiar la selección/contenido (TipTap v3 no
  // re-renderiza por sí solo), para que los estados activos y los controles de
  // tabla (Agregar/Eliminar fila) aparezcan al situar el cursor dentro de la matriz.
  const [, forceTick] = useState(0);
  useEffect(() => {
    if (!editor) return;
    const bump = () => forceTick((t) => t + 1);
    editor.on('selectionUpdate', bump);
    editor.on('transaction', bump);
    return () => {
      editor.off('selectionUpdate', bump);
      editor.off('transaction', bump);
    };
  }, [editor]);

  // Exponemos métodos imperativos para que el padre pueda insertar texto
  // (ej. variables {token}) en la posición exacta del cursor.
  useImperativeHandle(ref, () => ({
    insertText: (text) => {
      if (!editor || !text) return;
      editor.chain().focus().insertContent(String(text)).run();
    },
    focus: () => editor?.chain().focus().run(),
    getHTML: () => editor?.getHTML() || '',
  }), [editor]);

  if (!editor) return null;

  const plainLen = editor.getText().length;
  const pct = Math.min(100, (plainLen / maxChars) * 100);
  const overWarn = plainLen > maxChars * 0.9;
  const counterColor = plainLen >= maxChars ? 'text-rose-600' : overWarn ? 'text-orange-600' : 'text-slate-500';

  const addLink = () => {
    const previous = editor.getAttributes('link').href || '';
    const url = window.prompt('URL del enlace (incluya http:// o https://):', previous);
    if (url === null) return;
    if (url === '') { editor.chain().focus().extendMarkRange('link').unsetLink().run(); return; }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  };

  const Btn = ({ active, onClick, title, children, tid, disabled }) => (
    <button
      type="button"
      disabled={disabled}
      onMouseDown={(e) => { e.preventDefault(); if (!disabled) onClick(); }}
      title={title}
      data-testid={tid}
      className={cn(
        'h-7 w-7 rounded inline-flex items-center justify-center text-slate-600 hover:bg-slate-200 transition disabled:opacity-40',
        active && 'bg-indigo-100 text-indigo-700',
      )}
    >
      {children}
    </button>
  );

  return (
    <div className={cn('border border-slate-300 rounded-md bg-white overflow-hidden', tableRowActions && 'rte-actions')} data-testid={testid}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-0.5 border-b border-slate-200 bg-slate-50 px-2 py-1">
        <Btn active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} title="Negrita (Ctrl+B)" tid={`${testid}-bold`}><Bold size={14} /></Btn>
        <Btn active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} title="Cursiva (Ctrl+I)" tid={`${testid}-italic`}><Italic size={14} /></Btn>
        <Btn active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} title="Subrayado (Ctrl+U)" tid={`${testid}-underline`}><UnderlineIcon size={14} /></Btn>
        <Btn active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()} title="Tachado" tid={`${testid}-strike`}><Strikethrough size={14} /></Btn>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()} title="Lista con viñetas" tid={`${testid}-bullet`}><List size={14} /></Btn>
        <Btn active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Lista numerada" tid={`${testid}-ordered`}><ListOrdered size={14} /></Btn>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} title="Alinear izquierda" tid={`${testid}-align-left`}><AlignLeft size={14} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} title="Alinear centro" tid={`${testid}-align-center`}><AlignCenter size={14} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} title="Alinear derecha" tid={`${testid}-align-right`}><AlignRight size={14} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'justify' })} onClick={() => editor.chain().focus().setTextAlign('justify').run()} title="Justificar" tid={`${testid}-align-justify`}><AlignJustify size={14} /></Btn>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        {/* Color de fuente (native picker) */}
        <label className="relative inline-flex items-center justify-center h-7 w-7 rounded hover:bg-slate-200 cursor-pointer" title="Color de texto">
          <Palette size={14} className="text-slate-600" />
          <input
            type="color"
            onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
            className="absolute inset-0 opacity-0 cursor-pointer"
            data-testid={`${testid}-color`}
          />
        </label>

        {/* Color de fondo / Highlight (popover) */}
        <div className="relative">
          <Btn
            active={showHighlights || editor.isActive('highlight')}
            onClick={() => setShowHighlights((v) => !v)}
            title="Color de fondo (resaltar)"
            tid={`${testid}-highlight-toggle`}
          ><Highlighter size={14} /></Btn>
          {showHighlights && (
            <div
              className="absolute z-50 top-8 left-0 bg-white border border-slate-200 rounded-md shadow-lg p-1.5 flex gap-1"
              data-testid={`${testid}-highlight-palette`}
            >
              {BG_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { editor.chain().focus().toggleHighlight({ color: c }).run(); setShowHighlights(false); }}
                  className="w-5 h-5 rounded border border-slate-200 hover:scale-110 transition"
                  style={{ background: c }}
                  title={c}
                  data-testid={`${testid}-highlight-${c.replace('#', '')}`}
                />
              ))}
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { editor.chain().focus().unsetHighlight().run(); setShowHighlights(false); }}
                className="text-[10px] text-slate-500 hover:text-slate-700 px-1"
                title="Quitar resaltado"
              >×</button>
            </div>
          )}
        </div>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn active={editor.isActive('link')} onClick={addLink} title="Insertar enlace" tid={`${testid}-link`}><LinkIcon size={14} /></Btn>
        {enableImagePaste && (
          <Btn
            disabled={uploadingImage}
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
            title="Insertar imagen (o pega con Ctrl+V)"
            tid={`${testid}-image`}
          ><ImagePlus size={14} /></Btn>
        )}
        {enableImagePaste && (
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
            className="hidden"
            data-testid={`${testid}-image-input`}
            onChange={(e) => {
              const f = e.target.files && e.target.files[0];
              if (f) handleImageFile(f);
              e.target.value = '';
            }}
          />
        )}

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn onClick={() => editor.chain().focus().undo().run()} title="Deshacer (Ctrl+Z)" tid={`${testid}-undo`}><Undo2 size={14} /></Btn>
        <Btn onClick={() => editor.chain().focus().redo().run()} title="Rehacer (Ctrl+Y)" tid={`${testid}-redo`}><Redo2 size={14} /></Btn>

        {/* Controles de tabla — para la Matriz de Bancos/Productos (activos dentro de una tabla) */}
        <span className="mx-1 h-4 w-px bg-slate-300" />
        <Btn disabled={!editor.can().addRowAfter?.()} onClick={() => editor.chain().focus().addRowAfter().run()} title="Agregar fila debajo" tid={`${testid}-table-add-row`}><Rows3 size={14} /></Btn>
        <Btn disabled={!editor.can().deleteRow?.()} onClick={() => editor.chain().focus().deleteRow().run()} title="Eliminar fila" tid={`${testid}-table-del-row`}><Trash2 size={14} /></Btn>

        {showPreview && (
          <>
            <span className="flex-1" />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPreviewOpen(true)}
              className="h-7 text-xs gap-1"
              data-testid={`${testid}-preview-btn`}
            >
              <Eye size={13} /> Vista Previa
            </Button>
          </>
        )}
      </div>

      {/* Estilos de tabla dentro del editor (Matriz de Bancos/Productos editable) */}
      <style>{`
        [data-testid="${testid}"] .ProseMirror table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; table-layout: fixed; overflow: hidden; }
        [data-testid="${testid}"] .ProseMirror td, [data-testid="${testid}"] .ProseMirror th { border: 1px solid #d1d5db; padding: 6px 10px; vertical-align: top; position: relative; }
        [data-testid="${testid}"] .ProseMirror th { background: #2c3e50; color: #fff; text-align: left; font-weight: 600; }
        [data-testid="${testid}"] .ProseMirror .selectedCell:after { background: rgba(99,102,241,0.18); content: ""; position: absolute; inset: 0; pointer-events: none; }
        [data-testid="${testid}"] .ProseMirror table p { margin: 0; }
        [data-testid="${testid}"] .ProseMirror p { margin: 0 0 10px 0; line-height: 1.5; }
      `}</style>

      {/* Editor */}
      <EditorContent editor={editor} />
      {placeholder && plainLen === 0 && (
        <div className="px-3 pb-1 pt-0 -mt-10 text-sm text-slate-400 italic pointer-events-none">
          {placeholder}
        </div>
      )}

      {/* Counter */}
      <div className="flex items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-3 py-1">
        <div className="h-1 flex-1 bg-slate-200 rounded overflow-hidden">
          <div
            className={cn('h-full transition-all', pct >= 100 ? 'bg-rose-500' : pct > 90 ? 'bg-orange-500' : 'bg-indigo-500')}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={cn('text-[11px] font-medium tabular-nums whitespace-nowrap', counterColor)} data-testid={`${testid}-counter`}>
          {plainLen}/{maxChars}
        </span>
      </div>

      {showPreview && (
        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent className="max-w-2xl" data-testid={`${testid}-preview-dialog`}>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Eye className="text-blue-600" size={18} /> Vista Previa del Correo
              </DialogTitle>
            </DialogHeader>
            <div className="border rounded-lg p-4 bg-white max-h-[60vh] overflow-y-auto">
              <div
                className="email-render max-w-none"
                dangerouslySetInnerHTML={{ __html: substituteTokens(editor.getHTML(), exampleValues) }}
                data-testid={`${testid}-preview-body`}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPreviewOpen(false)}>
                <X size={14} className="mr-1" /> Cerrar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
});

/** Longitud de texto visible en un HTML. Sanitiza removiendo tags. */
export function htmlPlainLength(html) {
  if (!html) return 0;
  const s = String(html).replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
  return s.length;
}

export default RichTextEditor;
